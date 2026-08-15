from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryBoundaryTest(unittest.TestCase):
    def test_projection_manifest_declares_single_source_of_truth(self):
        manifest = json.loads((ROOT / "projection-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["role"], "projection_only")
        self.assertEqual(manifest["source_repository"], "KAFKA2306/cast_event_cal")
        contract = manifest["data_contract"]
        self.assertEqual(contract["canonical_ingestion"], "KAFKA2306/cast_event_cal")
        self.assertFalse(contract["classification_logic_in_this_repo"])
        self.assertFalse(contract["independent_collection_in_this_repo"])

    def test_canonical_flow_has_exactly_three_repository_kpis(self):
        text = (ROOT / "docs/canonical-flow.md").read_text(encoding="utf-8")
        expected = {
            "canonical_snapshot_acceptance_rate",
            "projection_freshness",
            "public_verification_success_rate",
        }
        found = {name for name in expected if f"`{name}`" in text}
        self.assertEqual(found, expected)
        self.assertIn("KAFKA2306/cast_event_cal", text)
        self.assertIn("receive -> parity validation -> static projection -> HTTP verification", text)

    def test_noncanonical_write_capable_research_workflow_is_absent(self):
        self.assertFalse((ROOT / ".github/workflows/weekly-repo-research.yml").exists())

    def test_cloudflare_routes_are_delivery_owned(self):
        routes = ROOT / "_routes.json"
        self.assertTrue(routes.is_file())
        payload = json.loads(routes.read_text(encoding="utf-8"))
        self.assertEqual(payload["version"], 1)
        workflow = (ROOT / ".github/workflows/deploy-canonical-pages-v2.yml").read_text(encoding="utf-8")
        self.assertIn("DELIVERY_OWNED_ASSETS = {'_routes.json'}", workflow)
        self.assertIn("if name in DELIVERY_OWNED_ASSETS:", workflow)


if __name__ == "__main__":
    unittest.main()
