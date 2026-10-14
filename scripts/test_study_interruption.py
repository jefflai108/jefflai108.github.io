"""Historical attestation is source-bound and cannot expose live/private data."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts import study_interruption as projection


class InterruptionTests(unittest.TestCase):
    def fixture(self,root):
        old=Path(__file__).resolve().parents[1]/'public/line-v3/line-always-on-planned-study-7b6e67afd463.public.json'
        plan=json.loads(old.read_text())
        rows=[{'path':f'source/engine/cache{i}.pyc','sha256':f'{i:064x}',
               'pinned_source_sha256':f'{i+100:064x}','code_equals_compile_of_pinned_source':True}
              for i in range(15)]
        incident={'generated_cache_count':15,'pinned_files_verified':3664,'plan_sha256':plan['proof']['plan_sha256'],
                  'caches':rows,'private_extra':'/Users/private/DO-NOT-PUBLISH'}
        restored={'removed_count':15,'unexpected_files':[],'pinned_files_verified':3664}
        protected={'pinned_bytes_verified':3664,'state_receipts_permissions_unchanged':True,
                   'source_and_harness_permissions':{'files':'0444','directories':'0555'}}
        inventory={'cache_count':15,'pinned_hash_mismatches':[],
                   'plan_sha256_now':plan['proof']['plan_sha256'],
                   'configuration_sha256_now':plan['proof']['configuration_sha256'],
                   'cache_inventory':[{'sha256':row['sha256'],'source_sha256':row['pinned_source_sha256'],
                       'manifest_source_sha256':row['pinned_source_sha256'],'cache_in_manifest':False} for row in rows],
                   'live_terminal':759,'private_paths':['/Users/private/DO-NOT-PUBLISH']}
        def write():
            for name,value in (('incident.private.json',incident),('restoration.json',restored),
                               ('read-only-snapshot-protection.json',protected),('inventory.json',inventory)):
                (root/name).write_text(json.dumps(value))
        write()
        return old,incident,restored,protected,inventory,write

    def test_only_historical_semantics_and_hash_proofs_are_exported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);old,*_rest=self.fixture(root)
            before={path.name:path.read_bytes() for path in root.iterdir()}
            value=projection.verified_projection(root,root/'inventory.json',old)
            self.assertEqual(before,{path.name:path.read_bytes() for path in root.iterdir()})
            text=json.dumps(value,ensure_ascii=False)
            self.assertNotIn('DO-NOT-PUBLISH',text);self.assertNotIn('live_terminal',text)
            self.assertNotIn('private_paths',text);self.assertNotIn('cache0.pyc',text)
            self.assertFalse(value['complete_study_result']);self.assertFalse(value['partial_scores_published'])
            self.assertEqual(value['proof']['original_planned_public_sha256'],projection.sha(old.read_bytes()))

    def test_foreign_source_config_removed_count_or_cache_identity_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);old,incident,restored,protected,inventory,write=self.fixture(root)
            for target,key,replacement in ((incident,'plan_sha256','a'*64),
                    (inventory,'configuration_sha256_now','a'*64),(restored,'removed_count',14),
                    (protected,'state_receipts_permissions_unchanged',False)):
                previous=deepcopy(target[key]);target[key]=replacement;write()
                with self.assertRaises(ValueError):projection.verified_projection(root,root/'inventory.json',old)
                target[key]=previous;write()
            inventory['cache_inventory'][0]['manifest_source_sha256']='a'*64;write()
            with self.assertRaisesRegex(ValueError,'cache_identity'):
                projection.verified_projection(root,root/'inventory.json',old)


if __name__=='__main__':unittest.main()
