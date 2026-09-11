#!/usr/bin/env bash
# Purge every image tag other than `snapshot` and `release` from the Nexus
# docker-hosted repository, for each Vireel module (backend, frontend,
# renderer).
#
# Why this exists: before the snapshot/release tagging strategy (see
# .github/workflows/ci-cd.yml and promote-release.yml), every push to main
# pushed a new, permanent `:<commit-sha>` tag that nothing ever removed --
# that's what filled Nexus with a long tail of images. Going forward, CI
# only ever pushes to the `snapshot` and `release` tags, so no new clutter
# accumulates on its own. This script is for the one-off cleanup of
# whatever already piled up, and can be re-run any time (it's idempotent:
# it does nothing if only snapshot/release exist).
#
# This talks to the Nexus REST API (v1/search + v1/components), which is a
# different endpoint than the Docker registry connector used by `docker
# push`/`docker pull` (NEXUS_REGISTRY in the workflows) -- it's Nexus's own
# web/admin API, normally on the main Nexus HTTP(S) port.
#
# Usage:
#   NEXUS_URL="https://nexus.example.com" \
#   NEXUS_REPOSITORY="docker-hosted" \
#   NEXUS_USERNAME="..." \
#   NEXUS_PASSWORD="..." \
#   ./scripts/nexus-cleanup.sh
#
# Add DRY_RUN=1 to only print what would be deleted, without deleting
# anything -- always run it that way first.
#
# Requires: curl, jq.

set -euo pipefail

: "${NEXUS_URL:?Set NEXUS_URL, e.g. https://nexus.example.com (the Nexus web/admin URL, not the Docker registry connector)}"
: "${NEXUS_REPOSITORY:?Set NEXUS_REPOSITORY to the Nexus repository name that hosts the docker images (e.g. docker-hosted)}"
: "${NEXUS_USERNAME:?Set NEXUS_USERNAME}"
: "${NEXUS_PASSWORD:?Set NEXUS_PASSWORD}"

IMAGE_PREFIX="${IMAGE_PREFIX:-vireel}"
KEEP_TAGS=("snapshot" "release")
DRY_RUN="${DRY_RUN:-0}"

for cmd in curl jq; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Missing required command: $cmd" >&2; exit 1; }
done

should_keep() {
  local tag="$1"
  for keep in "${KEEP_TAGS[@]}"; do
    [[ "$tag" == "$keep" ]] && return 0
  done
  return 1
}

cleanup_image() {
  local image_name="$1"
  echo "== ${image_name} (repository: ${NEXUS_REPOSITORY}) =="

  local continuation_token=""
  while :; do
    local url="${NEXUS_URL}/service/rest/v1/search?repository=${NEXUS_REPOSITORY}&name=${image_name}"
    [[ -n "$continuation_token" ]] && url="${url}&continuationToken=${continuation_token}"

    local response
    response=$(curl -sS -u "${NEXUS_USERNAME}:${NEXUS_PASSWORD}" "$url")

    local count
    count=$(echo "$response" | jq '.items | length')
    if [[ "$count" -eq 0 ]]; then
      break
    fi

    echo "$response" | jq -c '.items[] | {id, version}' | while read -r item; do
      local id version
      id=$(echo "$item" | jq -r '.id')
      version=$(echo "$item" | jq -r '.version')

      if should_keep "$version"; then
        echo "  keep   ${image_name}:${version}"
        continue
      fi

      if [[ "$DRY_RUN" == "1" ]]; then
        echo "  would delete ${image_name}:${version} (component id ${id})"
      else
        echo "  delete ${image_name}:${version} (component id ${id})"
        curl -sS -u "${NEXUS_USERNAME}:${NEXUS_PASSWORD}" -X DELETE \
          "${NEXUS_URL}/service/rest/v1/components/${id}" \
          -o /dev/null -w "    -> HTTP %{http_code}\n"
      fi
    done

    continuation_token=$(echo "$response" | jq -r '.continuationToken // empty')
    [[ -z "$continuation_token" ]] && break
  done
}

for service in backend frontend renderer; do
  cleanup_image "${IMAGE_PREFIX}-${service}"
done

echo
echo "Done. Tag deletion only removes the Nexus component/metadata -- the"
echo "underlying blobs are only actually reclaimed from disk once Nexus"
echo "runs its own blob-store cleanup task (Administration > Scheduled"
echo "Tasks > 'Compact blob store' / your repository's Cleanup Policy"
echo "task). Trigger that task once after the first run of this script if"
echo "you want the disk space back immediately."
