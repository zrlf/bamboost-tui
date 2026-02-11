from bamboost_tui.utils import get_index as get_index


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--color",
        "-c",
        action="store_false",
        default=True,
        help="Use full colors instead of terminal colors.",
    )
    parser.add_argument(
        "path",
        default=None,
        nargs="?",
    )
    from .app import BamboostApp

    args = parser.parse_args()

    app = BamboostApp(
        watch_css=True, ansi_color=args.color, initial_collection_path=args.path
    )
    app.run()
