"""Generate a draft, previewing replacement of a nonempty roster."""

import argparse

from scripts._common import add_database_option, database_service, print_summary, report_error


def main(argv: list[str] | None = None) -> int:
    """Generate into an empty roster or confirm a previewed replacement."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_database_option(parser)
    parser.add_argument("schedule_id", type=int)
    parser.add_argument("--confirm-replace", action="store_true", help="replace an existing roster")
    args = parser.parse_args(argv)
    try:
        service = database_service(args.db_name, must_exist=True)
        current = service.get_schedule(args.schedule_id)
        if current.state.assignments:
            preview = service.preview_generation(args.schedule_id)
            print(
                f"Replacement preview: {preview.removed_assignments} current, {preview.added_assignments} proposed assignments"
            )
            if not args.confirm_replace:
                print("Preview only; rerun with --confirm-replace to commit")
                print_summary(preview.draft)
                return 0
            result = service.confirm_generation(args.schedule_id, preview.token, confirmed=True)
            print("Roster replaced")
        else:
            result = service.generate(args.schedule_id)
            print("Draft generated")
        print_summary(result)
    except (ValueError, OSError) as error:
        return report_error(error)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
