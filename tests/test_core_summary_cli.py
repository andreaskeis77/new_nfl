
from new_nfl.cli import build_parser


def test_build_parser_accepts_summarize_core_command() -> None:
    parser = build_parser()

    args = parser.parse_args(['summarize-core', '--adapter-id', 'nflverse_bulk'])

    assert args.command == 'summarize-core'
    assert args.adapter_id == 'nflverse_bulk'
