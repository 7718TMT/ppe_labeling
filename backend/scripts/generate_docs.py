"""Generate configuration, API and database references, or check for drift."""

from backend.scripts import generate_api_docs, generate_configuration_docs, generate_database_docs
from backend.scripts._doc_utils import ROOT, parser, publish


def render(root=ROOT):
    outputs = {}
    for generator in (generate_configuration_docs, generate_api_docs, generate_database_docs):
        outputs.update(generator.render(root))
    return outputs


def main() -> int:
    args = parser(__doc__).parse_args()
    return publish(render(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
