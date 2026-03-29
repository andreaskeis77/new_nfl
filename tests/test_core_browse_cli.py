from new_nfl.cli import build_parser


def test_build_parser_accepts_browse_core_command() -> None:
    parser = build_parser()

    args = parser.parse_args(['browse-core', '--adapter-id', 'nflverse_bulk'])

    assert args.command == 'browse-core'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.field_prefix == ''
    assert args.data_type == ''
    assert args.limit == 20


def test_build_parser_accepts_browse_core_filters() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            'browse-core',
            '--adapter-id', 'nflverse_bulk',
            '--field-prefix', 'ga',
            '--data-type', 'numeric',
            '--limit', '5',
        ]
    )

    assert args.command == 'browse-core'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.field_prefix == 'ga'
    assert args.data_type == 'numeric'
    assert args.limit == 5
