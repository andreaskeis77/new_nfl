from new_nfl.cli import build_parser


def test_build_parser_accepts_core_load_command() -> None:
    parser = build_parser()

    args = parser.parse_args(['core-load', '--adapter-id', 'nflverse_bulk'])

    assert args.command == 'core-load'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.execute is False


def test_build_parser_accepts_core_load_execute_flag() -> None:
    parser = build_parser()

    args = parser.parse_args(['core-load', '--adapter-id', 'nflverse_bulk', '--execute'])

    assert args.command == 'core-load'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.execute is True
