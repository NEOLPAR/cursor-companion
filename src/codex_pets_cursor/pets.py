from __future__ import annotations

import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .paths import DOWNLOADS_DIR, PETS_DIR


@dataclass(frozen=True)
class Pet:
    id: str
    display_name: str
    description: str
    directory: Path
    spritesheet: Path


def _clean_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._").lower()
    return cleaned or "pet"


class PetStore:
    def __init__(self) -> None:
        PETS_DIR.mkdir(parents=True, exist_ok=True)
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    def list_pets(self) -> list[Pet]:
        pets: list[Pet] = []
        for pet_json in sorted(PETS_DIR.glob("*/pet.json")):
            pet = self._load_pet(pet_json.parent)
            if pet:
                pets.append(pet)
        return pets

    def get(self, pet_id: str | None) -> Pet | None:
        if not pet_id:
            return None
        return self._load_pet(PETS_DIR / pet_id)

    def remove(self, pet_id: str) -> None:
        shutil.rmtree(PETS_DIR / pet_id, ignore_errors=True)

    def import_directory(self, source: Path) -> Pet:
        pet_json = source / "pet.json"
        if not pet_json.exists():
            raise ValueError("Pet folder must contain pet.json")
        manifest = self._read_manifest(pet_json)
        pet_id = _clean_id(str(manifest.get("id") or source.name))
        target = self._unique_dir(pet_id)
        shutil.copytree(source, target)
        self._normalize_manifest(target, pet_id)
        pet = self._load_pet(target)
        if not pet:
            raise ValueError("Imported pet is missing a valid spritesheet")
        return pet

    def import_zip(self, zip_path: Path) -> Pet:
        if not zipfile.is_zipfile(zip_path):
            raise ValueError("Downloaded file is not a ZIP package")
        scratch = DOWNLOADS_DIR / f"import-{zip_path.stem}"
        shutil.rmtree(scratch, ignore_errors=True)
        scratch.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path) as archive:
                self._safe_extract(archive, scratch)
            package_dir = self._find_package_dir(scratch)
            return self.import_directory(package_dir)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def _load_pet(self, directory: Path) -> Pet | None:
        pet_json = directory / "pet.json"
        if not pet_json.exists():
            return None
        try:
            manifest = self._read_manifest(pet_json)
        except ValueError:
            return None
        spritesheet = directory / str(manifest.get("spritesheetPath", "spritesheet.webp"))
        if not spritesheet.exists():
            return None
        pet_id = _clean_id(str(manifest.get("id") or directory.name))
        return Pet(
            id=pet_id,
            display_name=str(manifest.get("displayName") or pet_id),
            description=str(manifest.get("description") or ""),
            directory=directory,
            spritesheet=spritesheet,
        )

    def _read_manifest(self, path: Path) -> dict:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid pet.json") from exc
        if not isinstance(data, dict):
            raise ValueError("pet.json must contain an object")
        return data

    def _normalize_manifest(self, directory: Path, pet_id: str) -> None:
        pet_json = directory / "pet.json"
        manifest = self._read_manifest(pet_json)
        manifest["id"] = pet_id
        pet_json.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def _unique_dir(self, pet_id: str) -> Path:
        target = PETS_DIR / pet_id
        if not target.exists():
            return target
        index = 2
        while (PETS_DIR / f"{pet_id}-{index}").exists():
            index += 1
        return PETS_DIR / f"{pet_id}-{index}"

    def _find_package_dir(self, root: Path) -> Path:
        matches = list(root.rglob("pet.json"))
        if not matches:
            raise ValueError("ZIP does not contain pet.json")
        return matches[0].parent

    def _safe_extract(self, archive: zipfile.ZipFile, destination: Path) -> None:
        root = destination.resolve()
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if root not in target.parents and target != root:
                raise ValueError("ZIP contains unsafe paths")
        archive.extractall(destination)
