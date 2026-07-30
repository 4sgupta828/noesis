"""noesis_vertical_regulatory — vertical #1 (regulatory commissions).

Reference implementation of the VerticalManifest. ALL regulatory vocabulary
(docket/case/utility/state/PUCO), connectors (incl. Ohio + residential fetch
strategy), extraction schema, authority policy, persona pack, and structured
tools live here — never in noesis_kernel.
"""

from .manifest import build_manifest

# The `noesis.verticals` entry point resolves to this. Built once at import
# (single-vertical-per-deployment, O3).
manifest = build_manifest()
