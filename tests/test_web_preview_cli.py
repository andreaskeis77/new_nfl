from new_nfl.cli import build_parser


def test_build_parser_accepts_render_web_preview_command() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            'render-web-preview',
            '--adapter-id',
            'nflverse_bulk',
            '--output',
            'data/exports/core_dictionary_preview.html',
        ]
    )

    assert args.command == 'render-web-preview'
    assert args.adapter_id == 'nflverse_bulk'
    assert args.output == 'data/exports/core_dictionary_preview.html'
    assert args.limit == 20
    assert args.data_type == ''


def test_build_parser_accepts_render_web_preview_optional_flags() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            'render-web-preview',
            '--adapter-id',
            'nflverse_bulk',
            '--output',
            'preview.html',
            '--limit',
            '5',
            '--data-type',
            'character',
        ]
    )

    assert args.command == 'render-web-preview'
    assert args.limit == 5
    assert args.data_type == 'character'
