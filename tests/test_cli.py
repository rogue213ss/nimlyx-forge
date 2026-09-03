import pytest
from click.testing import CliRunner
from backend.cli.main import cli
from backend.database.db import Base, engine
from backend.database.init_db import init_db

@pytest.fixture
def runner():
    # We should use a memory db for tests, but CLI creates its own session 
    # to the default db in SQLALCHEMY_DATABASE_URL which is sqlite:///./footage.db
    # For a real project we'd patch the engine, but for this audit test we can 
    # just test the error handling behavior using an invalid mapping ID.
    return CliRunner()

def test_cli_set_timestamps_invalid_mapping(runner):
    result = runner.invoke(cli, ['set-timestamps', '--mapping-id', '999999', '--start', '5.0', '--end', '10.0'])
    assert result.exit_code != 0
    assert "Mapping not found" in result.output

def test_cli_update_mapping_invalid_state(runner):
    # Pass an invalid state string (click validation should catch this)
    result = runner.invoke(cli, ['update-mapping', '--mapping-id', '1', '--state', 'INVALID_STATE'])
    assert result.exit_code != 0
    assert "Invalid value for '--state'" in result.output
