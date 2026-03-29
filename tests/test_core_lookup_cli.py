from new_nfl.cli import build_parser


def test_build_parser_accepts_describe_core_field_command() -> None:
    parser = build_parser()

    args = parser.parse_args(
        ['describe-core-field', '--adapter-id', 'nflverse_bulk', '--field', 'game_id']
    )

    assert args.command == 'describe-core-field'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.field == 'game_id'


def test_build_parser_requires_field_for_describe_core_field() -> None:
    parser = build_parser()

    try:
        parser.parse_args(['describe-core-field', '--adapter-id', 'nflverse_bulk'])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError('expected parser to reject missing --field')
