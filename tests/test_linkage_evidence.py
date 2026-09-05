"""Small offline publisher fixtures; no large workbook or sibling repo required."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import build_linkage_evidence as builder


def publisher(eid='2000-0001-AAA', external='DFO:1', start='2000-01-01', end='2000-01-03', country='Example'):
    result = {field: '' for field in builder.FIELDS}
    result.update({'DisNo.': eid, 'External IDs': external, 'Country': country, 'ISO': 'AAA',
                   'Location': 'Example location', 'Disaster Type': 'Flood', 'workbook_row': '2'})
    for side, value in [('Start', start), ('End', end)]:
        for name, component in zip(('Year', 'Month', 'Day'), value.split('-')):
            result[f'{side} {name}'] = str(int(component))
    return result


def raw(rid='2000-0001-AAA', source='EM-DAT', start='2000-01-01', end='2000-01-03', country='Example'):
    return dict(source=source, source_id=rid, country=country, iso='AAA', start_date=start, end_date=end,
                deaths='10', match_group_id='3.0')


def workbook(path, rows):
    headers = ['Disaster Type'] + builder.FIELDS
    root = ET.Element(builder.NS + 'worksheet')
    data = ET.SubElement(root, builder.NS + 'sheetData')
    values = [headers] + [[row.get(field, '') for field in headers] for row in rows]
    for number, values_row in enumerate(values, 1):
        row = ET.SubElement(data, builder.NS + 'row', r=str(number))
        for column, value in enumerate(values_row):
            cell = ET.SubElement(row, builder.NS + 'c', r=f'{chr(65+column)}{number}', t='inlineStr')
            inline = ET.SubElement(cell, builder.NS + 'is')
            ET.SubElement(inline, builder.NS + 't').text = value
    with ZipFile(path, 'w') as archive:
        archive.writestr('xl/worksheets/sheet1.xml', ET.tostring(root))


class LinkageEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_workbook_extraction_preserves_external_ids_blank_precision_and_row_evidence(self):
        entry = publisher(external='DFO:1|GLIDE:FL-2000-000001')
        entry['Start Day'] = ''
        storm = publisher('2000-0002-AAA'); storm['Disaster Type'] = 'Storm'
        path = self.root / 'small.xlsx'; workbook(path, [entry, storm])
        rows = builder.publisher_rows(path)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['External IDs'], entry['External IDs'])
        self.assertEqual(rows[0]['Start Day'], '')
        self.assertEqual(rows[0]['workbook_row'], '2')
        self.assertIsNone(builder.exact_publisher_interval(rows[0]))

    def test_publisher_link_requires_country_date_and_target_consistency(self):
        catalog = [raw(), raw('DFO-1', 'DFO')]
        good = builder.validate_publisher_links([publisher()], catalog)
        self.assertEqual(good[0]['status'], 'accepted')
        cases = [([raw(), raw('DFO-1', 'DFO', country='Elsewhere')], publisher(), 'country_mismatch'),
                 ([raw(), raw('DFO-1', 'DFO', start='2001-01-01', end='2001-01-03')], publisher(), 'no_date_overlap'),
                 ([raw()], publisher(), 'missing_target')]
        for rows, entry, reason in cases:
            with self.subTest(reason=reason):
                result = builder.validate_publisher_links([entry], rows)[0]
                self.assertEqual(result['status'], 'rejected')
                self.assertIn(reason, result['reasons'])
        incomplete = publisher(); incomplete['Start Day'] = ''
        self.assertIn('incomplete_publisher_date', builder.validate_publisher_links([incomplete], catalog)[0]['reasons'])

    def test_one_dfo_id_cannot_join_different_publisher_event_identities(self):
        entries = [publisher(), publisher('2000-0002-AAA')]
        catalog = [raw(), raw('2000-0002-AAA'), raw('DFO-1', 'DFO')]
        ledger = builder.validate_publisher_links(entries, catalog)
        self.assertTrue(all(row['status'] == 'rejected' for row in ledger))
        self.assertTrue(all(row['reasons'] == 'dfo_multiple_emdat_events' for row in ledger))

    def test_reviewed_brazil_split_preserves_every_member_and_uncertain_remaining_pair(self):
        first = publisher('2024-0108-BRA', '', '2024-02-13', '2024-02-16', 'Brazil')
        first['Location'] = 'Macapá Municipality (Amapá State)'
        second = publisher('2024-0098-BRA', '', '2024-02-21', '2024-02-23', 'Brazil')
        second['Location'] = 'Municipalities (Rio de Janeiro State);'
        rows = [raw(first['DisNo.'], start='2024-02-13', end='2024-02-16', country='Brazil'),
                raw(second['DisNo.'], start='2024-02-21', end='2024-02-23', country='Brazil'),
                raw('DFO-5516', 'DFO', '2024-02-21', '2024-02-22', 'Brazil')]
        with patch.object(builder, 'APPROVED_PUBLISHER_GROUPS', set()):
            correction = builder.correction_groups(rows, [first, second], [])[0]
        self.assertEqual(len(correction['records']), 3)
        self.assertEqual(len({row['canonical_event_id'] for row in correction['records']}), 2)
        self.assertEqual(correction['method'], 'reviewed_date_geography_split')
        self.assertIn('unconfirmed', correction['reason'])

    def test_unknown_source_hash_fails_without_creating_evidence(self):
        (self.root / 'merged_floods_long.csv').write_text('source,source_id\nEM-DAT,test\n')
        (self.root / 'emdat_all_disasters_2026-05-18.xlsx').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'source hash changed'):
            builder.build(self.root)
        self.assertFalse((self.root / 'flood_linkage_evidence').exists())


if __name__ == '__main__':
    unittest.main()
