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
    from .app import BamboostApp
    args = parser.parse_args()

    BamboostApp(watch_css=True, ansi_color=args.color).run()
