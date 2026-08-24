#!/bin/bash
set -e

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORCE=false

# Argumente parsen
while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE=true
            shift
            ;;
        *)
            echo -e "${RED}Unbekanntes Argument: $1${NC}"
            echo "Verwendung: $0 [--force|-f]"
            exit 1
            ;;
    esac
done

# Funktion: Ordnergröße berechnen
get_size() {
    local path="$1"
    if [[ -e "$path" ]]; then
        du -sh "$path" 2>/dev/null | cut -f1 || echo "0"
    else
        echo "0"
    fi
}

# Funktion: Dateien in Ordner löschen (Ordner behalten)
clear_dir() {
    local dir="$1"
    if [[ -d "$dir" ]]; then
        find "$dir" -mindepth 1 -delete 2>/dev/null || true
    fi
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}     YouTube Kanal Scraper - Reset     ${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Speicherplatz berechnen
echo -e "${YELLOW}Berechne Speicherplatz...${NC}"
echo ""

YTLIB_DATA="$SCRIPT_DIR/data"

size_ytlib_videos=$(get_size "$YTLIB_DATA/videos")
size_ytlib_audio=$(get_size "$YTLIB_DATA/audio")
size_ytlib_transcripts=$(get_size "$YTLIB_DATA/transcripts")
size_ytlib_refined=$(get_size "$YTLIB_DATA/transcripts_refined")

echo -e "${BLUE}youtube-library:${NC}"
echo "  data/videos:             $size_ytlib_videos"
echo "  data/audio:              $size_ytlib_audio"
echo "  data/transcripts:        $size_ytlib_transcripts"
echo "  data/transcripts_refined: $size_ytlib_refined"
echo "  + Docker Volumes (PostgreSQL, Qdrant)"
echo ""

# Bestätigung
if [[ "$FORCE" != true ]]; then
    echo -e "${RED}WARNUNG: Alle Daten werden unwiderruflich gelöscht!${NC}"
    echo ""
    read -p "Fortfahren? (ja/nein): " confirm
    if [[ "$confirm" != "ja" ]]; then
        echo -e "${YELLOW}Abgebrochen.${NC}"
        exit 0
    fi
    echo ""
fi

# 1. youtube-library zurücksetzen
echo -e "${BLUE}[1/2] youtube-library zurücksetzen...${NC}"

cd "$SCRIPT_DIR"
if docker compose ps -q 2>/dev/null | grep -q .; then
    echo "  Docker Container stoppen..."
    docker compose down -v 2>/dev/null || true
else
    echo "  Keine laufenden Container gefunden"
    # Volumes trotzdem löschen falls vorhanden
    docker compose down -v 2>/dev/null || true
fi

echo "  Datenordner leeren..."
clear_dir "$YTLIB_DATA/videos"
clear_dir "$YTLIB_DATA/audio"
clear_dir "$YTLIB_DATA/transcripts"
clear_dir "$YTLIB_DATA/transcripts_refined"

echo -e "${GREEN}  Erledigt!${NC}"
echo ""

# 2. Zusammenfassung
echo -e "${BLUE}[2/2] Abgeschlossen!${NC}"
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}     Reset erfolgreich abgeschlossen    ${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Gelöscht:"
echo "  - Docker Container und Volumes (PostgreSQL, Qdrant)"
echo "  - Alle Videos und Audio-Dateien"
echo "  - Alle Transkripte (roh und verfeinert)"
echo ""
echo -e "${YELLOW}Hinweis: Ordnerstruktur wurde beibehalten.${NC}"
echo -e "${YELLOW}Zum Neustart: ./start.sh${NC}"
