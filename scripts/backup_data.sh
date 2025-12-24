#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/backups}"
DOC_PATH_ENV="${DOC_PATH:-${ROOT_DIR}/my-docs}"

mkdir -p "${BACKUP_DIR}"

timestamp=$(date +"%Y%m%d_%H%M%S")
backup_file="${BACKUP_DIR}/gptr_backup_${timestamp}.tar.gz"

paths=("outputs" "logs")

if [[ -d "${DOC_PATH_ENV}" ]]; then
  if [[ "${DOC_PATH_ENV}" == "${ROOT_DIR}"* ]]; then
    rel_path="${DOC_PATH_ENV#${ROOT_DIR}/}"
    paths+=("${rel_path}")
  else
    echo "WARN: DOC_PATH is outside repo, not included: ${DOC_PATH_ENV}" >&2
  fi
else
  echo "WARN: DOC_PATH not found, skipping: ${DOC_PATH_ENV}" >&2
fi

if [[ ! -d "${ROOT_DIR}/outputs" ]]; then
  mkdir -p "${ROOT_DIR}/outputs"
fi
if [[ ! -d "${ROOT_DIR}/logs" ]]; then
  mkdir -p "${ROOT_DIR}/logs"
fi

tar -czf "${backup_file}" -C "${ROOT_DIR}" "${paths[@]}"

echo "Backup created: ${backup_file}"
