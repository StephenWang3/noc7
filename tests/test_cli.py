from noc7.cli import main


def test_committed_json_schemas_are_up_to_date(root, monkeypatch):
    monkeypatch.chdir(root)
    assert main(["schema", "check"]) == 0


def test_cli_validates_all_bundles_and_gold(root, monkeypatch):
    monkeypatch.chdir(root)
    assert main(["bundle", "validate"]) == 0
    assert main(["gold", "check"]) == 0
