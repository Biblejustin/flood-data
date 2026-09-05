#!/usr/bin/env python3
"""Reproduce eleven reviewed flood-block splits from unchanged publisher inputs.

The original matching program is unavailable. Existing blocks are not evidence
that every member is the same event. This bounded correction uses publisher IDs
and exact retained dates; it does not reconstruct a general fuzzy matcher.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

BASE = Path(__file__).resolve().parent
REVIEWED_CATALOG_SHA256 = '27ce3522601d593ac6d85e746288195b8f277e2da3b348e39763b56cd24e21fd'
REVIEWED_WORKBOOK_SHA256 = 'fbf43fe73135aa57423a6b8614ba05ae27f67e812266a465b8bef4a209989742'
APPROVED_PUBLISHER_GROUPS = {'299.0', '300.0', '437.0', '459.0', '462.0', '567.0', '572.0', '598.0', '648.0', '652.0'}
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
FIELDS = ['DisNo.', 'External IDs', 'Country', 'ISO', 'Location',
          'Start Year', 'Start Month', 'Start Day', 'End Year', 'End Month', 'End Day']


def digest(content):
    return hashlib.sha256(content).hexdigest()


def record_digest(row):
    return digest(json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode())


def publisher_rows(workbook):
    """Read exact cell values using stdlib; blank day fields remain blank."""
    rows = []
    with ZipFile(workbook) as archive:
        shared = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            shared = [''.join(item.itertext()) for item in ET.fromstring(archive.read('xl/sharedStrings.xml')).findall(NS + 'si')]
        headers = None
        for _, element in ET.iterparse(archive.open('xl/worksheets/sheet1.xml'), events=['end']):
            if element.tag != NS + 'row':
                continue
            cells = {}
            for cell in element.findall(NS + 'c'):
                value = cell.find(NS + 'v')
                inline = cell.find(NS + 'is')
                value = value.text if value is not None else ''.join(inline.itertext()) if inline is not None else ''
                if cell.get('t') == 's':
                    value = shared[int(value)]
                cells[re.sub(r'\d+', '', cell.attrib['r'])] = value or ''
            if headers is None:
                headers = cells
                if not set(FIELDS + ['Disaster Type']) <= set(headers.values()):
                    raise ValueError('Publisher workbook lacks required linkage/date fields')
            else:
                row = {headers[column]: value for column, value in cells.items() if column in headers}
                if row.get('Disaster Type') == 'Flood':
                    rows.append({field: row.get(field, '') for field in FIELDS} |
                                {'workbook_row': element.attrib['r'], 'worksheet_part': 'xl/worksheets/sheet1.xml'})
            element.clear()
    identities = [row['DisNo.'] for row in rows]
    if not rows or any(not identity for identity in identities) or len(set(identities)) != len(identities):
        raise ValueError('Publisher flood IDs must be nonempty and unique')
    return rows


def exact_publisher_interval(row):
    values = [row.get(f'{side} {part}', '') for side in ('Start', 'End') for part in ('Year', 'Month', 'Day')]
    if not all(values):
        return None
    try:
        values = [int(value) for value in values]
        return date(*values[:3]), date(*values[3:])
    except (TypeError, ValueError):
        return None


def source_interval(row):
    try:
        return date.fromisoformat(row['start_date']), date.fromisoformat(row['end_date'])
    except (KeyError, TypeError, ValueError):
        return None


def core(source_id):
    return re.sub(r'-[A-Z]{3}$', '', source_id)


def overlaps(first, second):
    return first[0] <= second[1] and second[0] <= first[1]


def validate_publisher_links(published, catalog):
    lookup = {(row['source'], row['source_id']): row for row in catalog}
    ledger = []
    for published_row in published:
        for item in published_row['External IDs'].split('|'):
            if not item.strip().startswith('DFO:'):
                continue
            value = item.split(':', 1)[1].strip().removeprefix('DFO-')
            source_id = 'DFO-' + value
            reasons = []
            emdat = lookup.get(('EM-DAT', published_row['DisNo.']))
            dfo = lookup.get(('DFO', source_id))
            interval = exact_publisher_interval(published_row)
            if not re.fullmatch(r'\d+', value):
                reasons.append('invalid_external_id')
            if interval is None:
                reasons.append('incomplete_publisher_date')
            if emdat is None:
                reasons.append('missing_emdat_record')
            elif interval is not None and source_interval(emdat) != interval:
                reasons.append('publisher_catalog_date_disagreement')
            if dfo is None:
                reasons.append('missing_target')
            elif emdat is not None:
                if emdat['country'] not in [name.strip() for name in dfo['country'].split('•')]:
                    reasons.append('country_mismatch')
                first, second = source_interval(emdat), source_interval(dfo)
                if first is None or second is None:
                    reasons.append('invalid_date')
                elif first[1] < first[0] or second[1] < second[0]:
                    reasons.append('invalid_interval')
                elif not overlaps(first, second):
                    reasons.append('no_date_overlap')
            ledger.append(dict(emdat_id=published_row['DisNo.'], emdat_event_id=core(published_row['DisNo.']),
                               dfo_id=source_id, publisher_external_ids=published_row['External IDs'],
                               workbook_row=published_row['workbook_row'],
                               emdat_country=emdat['country'] if emdat else '', dfo_country=dfo['country'] if dfo else '',
                               emdat_start=emdat['start_date'] if emdat else '', emdat_end=emdat['end_date'] if emdat else '',
                               dfo_start=dfo['start_date'] if dfo else '', dfo_end=dfo['end_date'] if dfo else '',
                               status='rejected' if reasons else 'accepted', reasons=';'.join(sorted(set(reasons)))))
    targets = {}
    for row in ledger:
        if row['status'] == 'accepted':
            targets.setdefault(row['dfo_id'], set()).add(row['emdat_event_id'])
    for row in ledger:
        if row['status'] == 'accepted' and len(targets[row['dfo_id']]) > 1:
            row.update(status='rejected', reasons='dfo_multiple_emdat_events')
    return sorted(ledger, key=lambda row: (row['emdat_id'], row['dfo_id']))


def correction_groups(catalog, published, ledger):
    publisher = {row['DisNo.']: row for row in published}
    accepted = {row['dfo_id']: row['emdat_event_id'] for row in ledger if row['status'] == 'accepted'}
    groups = {}
    for row in catalog:
        if row['match_group_id']:
            groups.setdefault(str(float(row['match_group_id'])), []).append(row)
    corrections = []
    for group_id in sorted(APPROVED_PUBLISHER_GROUPS | {'3.0'}, key=float):
        members = groups.get(group_id, [])
        emdat = [row for row in members if row['source'] == 'EM-DAT']
        dfo = [row for row in members if row['source'] == 'DFO']
        cores = {core(row['source_id']) for row in emdat}
        if len(cores) != 2 or len(emdat) + len(dfo) != len(members):
            raise ValueError(f'Reviewed group {group_id} membership changed')
        for row in emdat:
            published_row = publisher.get(row['source_id'])
            if published_row is None or exact_publisher_interval(published_row) != source_interval(row):
                raise ValueError(f'Incomplete or inconsistent original date for {row["source_id"]}')
        if any(core(a['source_id']) != core(b['source_id']) and overlaps(source_interval(a), source_interval(b))
               for a in emdat for b in emdat):
            raise ValueError(f'Reviewed group {group_id} contains overlapping distinct publisher events')
        assignments = {('EM-DAT', row['source_id']): core(row['source_id']) for row in emdat}
        if group_id == '3.0':
            expected = {'2024-0108-BRA', '2024-0098-BRA', 'DFO-5516'}
            if {row['source_id'] for row in members} != expected:
                raise ValueError('Reviewed Brazil group membership changed')
            if publisher['2024-0108-BRA']['Location'] != 'Macapá Municipality (Amapá State)' or 'Rio de Janeiro State' not in publisher['2024-0098-BRA']['Location']:
                raise ValueError('Reviewed Brazil location evidence changed')
            assignments[('DFO', 'DFO-5516')] = '2024-0098'
            reason = 'Separate original Macapa Feb13-16 event from Rio de Janeiro Feb21-23 event; retain existing DFO5516/Rio pair without upgrading its unconfirmed linkage status.'
            method = 'reviewed_date_geography_split'
        else:
            for row in dfo:
                assigned = accepted.get(row['source_id'])
                if assigned not in cores:
                    raise ValueError(f'Unresolved DFO member in reviewed group {group_id}')
                assignments[('DFO', row['source_id'])] = assigned
            reason = 'Publisher DFO references assign every DFO member; distinct complete-date EM-DAT event intervals are separate.'
            method = 'publisher_id_and_temporal_separation'
        for row in dfo:
            assigned = assignments[('DFO', row['source_id'])]
            if any(core(other['source_id']) != assigned and overlaps(source_interval(row), source_interval(other)) for other in emdat):
                raise ValueError(f'DFO member overlaps a different event in reviewed group {group_id}')
        corrections.append(dict(legacy_match_group_id=group_id, method=method, reason=reason,
                                publisher_evidence=[publisher[row['source_id']] for row in emdat],
                                records=[dict(source=row['source'], source_id=row['source_id'],
                                              row_sha256=record_digest(row),
                                              canonical_event_id=f'split:{group_id}:emdat:{assignments[(row["source"], row["source_id"])]}')
                                         for row in sorted(members, key=lambda row: (row['source'], row['source_id']))]))
    return corrections


def csv_bytes(rows):
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=list(rows[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode()


def write_changed(path, content):
    if path.exists() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_bytes(content)
    temporary.replace(path)


def build(source_root=BASE, mirror_catalog=None):
    root = Path(source_root)
    workbook = root / 'emdat_all_disasters_2026-05-18.xlsx'
    catalog_path = root / 'merged_floods_long.csv'
    catalog_bytes = catalog_path.read_bytes()
    if digest(catalog_bytes) != REVIEWED_CATALOG_SHA256 or digest(workbook.read_bytes()) != REVIEWED_WORKBOOK_SHA256:
        raise ValueError('Reviewed source hash changed; linkage corrections require source adjudication before regeneration')
    catalog = list(csv.DictReader(io.StringIO(catalog_bytes.decode())))
    published = publisher_rows(workbook)
    ledger = validate_publisher_links(published, catalog)
    corrections = correction_groups(catalog, published, ledger)
    files = {'flood_linkage_evidence/emdat_publisher_metadata.csv': csv_bytes(published),
             'flood_linkage_evidence/publisher_dfo_links.csv': csv_bytes(ledger)}
    contract = dict(schema_version=1, catalog_sha256=digest(catalog_bytes), raw_rows=len(catalog),
                    publisher_workbook=workbook.name, publisher_workbook_sha256=REVIEWED_WORKBOOK_SHA256,
                    publisher_documentation='https://doc.emdat.be/docs/data-structure-and-content/emdat-public-table/',
                    publisher_link_ledger='flood_linkage_evidence/publisher_dfo_links.csv',
                    evidence_sha256={name: digest(content) for name, content in files.items()},
                    counts=dict(publisher_flood_rows=len(published), catalog_emdat_rows=sum(row['source'] == 'EM-DAT' for row in catalog),
                                accepted_publisher_links=sum(row['status'] == 'accepted' for row in ledger),
                                rejected_publisher_links=sum(row['status'] == 'rejected' for row in ledger),
                                corrected_legacy_groups=len(corrections), corrected_source_rows=sum(len(group['records']) for group in corrections)),
                    corrections=corrections,
                    limitations=['Correction units follow reviewed catalog identities; they do not establish physically independent disasters.',
                                 'Only eleven reviewed blocks are split. Every other legacy grouping and uncertain residual is preserved.',
                                 'Publisher references that fail date, country, precision or identity checks remain in the rejected ledger.',
                                 'The workbook has fewer flood rows than the later catalog; absent publisher metadata is unknown.',
                                 'No death totals are added, missing deaths remain unknown, and catalog coverage is not extended.'])
    contract_bytes = (json.dumps(contract, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + '\n').encode()
    destinations = [(root, catalog_path.name + '.linkage.json')]
    if mirror_catalog is not None:
        mirror_catalog = Path(mirror_catalog)
        if digest(mirror_catalog.read_bytes()) != contract['catalog_sha256']:
            raise ValueError('Central raw catalog differs from reviewed feeder source')
        destinations.append((mirror_catalog.parent, mirror_catalog.name + '.linkage.json'))
    for destination, contract_name in destinations:
        for name, content in files.items():
            write_changed(destination / name, content)
        write_changed(destination / contract_name, contract_bytes)
    return contract


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mirror-catalog', type=Path, help='Also write evidence beside an identical central raw CSV')
    args = parser.parse_args()
    print(json.dumps(build(mirror_catalog=args.mirror_catalog)['counts'], indent=2))
