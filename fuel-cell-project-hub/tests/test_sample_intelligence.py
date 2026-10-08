"""Synthetic unit fixtures test edge cases; acceptance uses the actual archive."""
import unittest
from tests import test_research_workspace as fixtures
from app.services.sample_intelligence import normalize, classify_image, SampleIntelligence
from app.services.formatting import format_file_size


class IntelligenceTests(unittest.TestCase):
    setUp=fixtures.WorkspaceTests.setUp
    tearDown=fixtures.WorkspaceTests.tearDown
    def test_normalization_sizes_and_numeric_disambiguation(self):
        self.assertEqual(normalize('HOLY_GDL'),normalize('Holy-GDL'))
        for value,want in [(851,'851 B'),(123456,'123 KB'),(3280000,'3.28 MB'),(999999,'1 MB'),(0,'0 B')]:
            self.assertEqual(format_file_size(value),want)
        for name in ('1344_results.csv','dimensions_1344.png','date_20261344.txt'):
            (self.legacy/name).write_text('fixture')
        self.catalog.refresh(quick=True)
        self.assertEqual(self.repo.objects('sample','legacy'),[])

    def test_family_subtypes_alias_filters_and_manual_rescan_preservation(self):
        for name in ('Holy_001_original.png','Holy_001_overlay.png','Holy_001_pore_map.png','Holy_001_numbered_outlines.png',
                     '1344Pa_a_original.png','1344Pa_a_pore_map.png','1344Pa_a_outline.png'):
            (self.legacy/name).write_text('unit fixture, not a real image')
        self.catalog.refresh(quick=True)
        samples=self.repo.objects('sample','legacy')
        self.assertEqual({s['name'] for s in samples},{'Holy GDL','1344 Pascal'})
        holy=next(s for s in samples if s['name']=='Holy GDL')
        rows,total=self.catalog.query('Holy GDL',origin='legacy',family='Images',sample=holy['id'])
        self.assertEqual(total,4)
        self.assertEqual(self.catalog.query(origin='legacy',sample=holy['id'],image_subcategory='Pore Map',extension='.png')[1],1)
        generated=self.catalog.query(origin='legacy',sample=holy['id'],image_category='Generated / Processed')[0]
        self.assertEqual(len(generated),3)
        service=SampleIntelligence(self.catalog)
        self.assertEqual(len(service.family_members(generated[0]['id'])),4)
        self.assertEqual(self.catalog.query(origin='legacy',sample=holy['id'],group_families=True)[1],1)
        service.assign(generated[0]['id'],[])
        service.edit_image(generated[0]['id'],'Reference')
        self.catalog.refresh(quick=True)
        self.assertEqual(service.related_samples(generated[0]['id']),[])
        with self.catalog.connect() as db:
            self.assertEqual(db.execute('SELECT image_category FROM image_assets WHERE file_id=?',(generated[0]['id'],)).fetchone()[0],'Reference')
        with self.assertRaises(ValueError):service.assign(self.row['id'],[holy['id']])

    def test_multi_sample_report_and_filename_priority(self):
        for name in ('Holy_001_original.tif','Holy_002_original.tif','Holy_003_original.tif','1344Pa_a.tif','1344Pa_b.tif','1344Pa_c.tif','HolyGDL_1344Pa_comparison.pdf'):
            (self.legacy/name).write_text('fixture')
        self.catalog.refresh(quick=True)
        row=self.catalog.query('comparison',origin='legacy')[0][0]
        service=SampleIntelligence(self.catalog)
        self.assertEqual(len(service.related_samples(row['id'])),2)
        samples=self.repo.objects('sample','legacy')
        for sample in samples:
            self.assertEqual(self.catalog.query(sample=sample['id'],family='Reports',explicit=True)[1],1)
        service.assign(row['id'],[s['id'] for s in samples],'compares')
        self.catalog.refresh(quick=True)
        self.assertTrue(all(s['manually_confirmed'] for s in service.related_samples(row['id'])))

    def test_categories_do_not_invent_processing(self):
        self.assertEqual(classify_image('photo.jpg')[0],'Unknown')
        self.assertEqual(classify_image('sample_pore_map.png')[1],'Pore Map')
        self.assertEqual(classify_image('sample_overlay.png')[1],'Overlay')
        self.assertEqual(classify_image('Drawing of sample.tif')[1],'Outline')
