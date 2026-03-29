from new_nfl.cli import build_parser


def test_build_parser_accepts_serve_web_preview_command() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            'serve-web-preview',
            '--adapter-id',
            'nflverse_bulk',
        ]
    )

    assert args.command == 'serve-web-preview'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.host == '127.0.0.1'
    assert args.port == 8787
    assert args.limit == 20
    assert args.data_type == ''


def test_build_parser_accepts_serve_web_preview_optional_flags() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            'serve-web-preview',
            '--adapter-id',
            'nflverse_bulk',
            '--host',
            '0.0.0.0',
            '--port',
            '8790',
            '--limit',
            '5',
            '--data-type',
            'character',
        ]
    )

    assert args.command == 'serve-web-preview'
    assert args.host == '0.0.0.0'
    assert args.port == 8790
    assert args.limit == 5
    assert args.data_type == 'character'
