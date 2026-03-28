from new_nfl.cli import build_parser


def test_cli_parser_includes_new_adapter_commands() -> None:
    parser = build_parser()

    parsed = parser.parse_args(['list-adapters'])
    assert parsed.command == 'list-adapters'

    described = parser.parse_args(['describe-adapter', '--adapter-id', 'nflverse_bulk'])
    assert described.command == 'describe-adapter'
    assert described.adapter_id == 'nflverse_bulk'

    stage_loaded = parser.parse_args(['stage-load', '--adapter-id', 'nflverse_bulk'])
    assert stage_loaded.command == 'stage-load'
    assert stage_loaded.adapter_id == 'nflverse_bulk'
