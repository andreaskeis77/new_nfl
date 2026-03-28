from new_nfl.cli import build_parser


def test_cli_parser_includes_fetch_contract_commands() -> None:
    parser = build_parser()

    run_parsed = parser.parse_args(['run-adapter', '--adapter-id', 'nflverse_bulk'])
    assert run_parsed.command == 'run-adapter'
    assert run_parsed.adapter_id == 'nflverse_bulk'
    assert run_parsed.execute is False

    execute_parsed = parser.parse_args(
        ['run-adapter', '--adapter-id', 'nflverse_bulk', '--execute']
    )
    assert execute_parsed.command == 'run-adapter'
    assert execute_parsed.execute is True

    listed = parser.parse_args(
        ['list-ingest-runs', '--pipeline-name', 'adapter.nflverse_bulk.fetch']
    )
    assert listed.command == 'list-ingest-runs'
    assert listed.pipeline_name == 'adapter.nflverse_bulk.fetch'
