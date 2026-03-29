from new_nfl.cli import build_parser


def test_build_parser_accepts_browse_core_command() -> None:
    parser = build_parser()

    args = parser.parse_args(['browse-core', '--adapter-id', 'nflverse_bulk'])

    assert args.command == 'browse-core'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.limit == 20
    assert args.field_prefix == ''


def test_build_parser_accepts_browse_core_options() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            'browse-core',
            '--adapter-id',
            'nflverse_bulk',
            '--limit',
            '5',
            '--field-prefix',
            'ga',
        ]
    )

    assert args.command == 'browse-core'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.limit == 5
    assert args.field_prefix == 'ga'
