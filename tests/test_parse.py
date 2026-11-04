import zipfile
from datetime import datetime

import pyarrow.parquet as pq

from fuelwatch import parse

# Deux stations : une complète (avec accents), une sans horaires ni coordonnées.
XML = """<?xml version="1.0" encoding="ISO-8859-1" standalone="yes"?>
<pdv_liste>
  <pdv id="1000001" latitude="4620100" longitude="519800" cp="01000" pop="R">
    <adresse>596 AVENUE DE TREVOUX</adresse>
    <ville>SAINT-DENIS-LÈS-BOURG</ville>
    <horaires automate-24-24="1"></horaires>
    <services>
      <service>Station de gonflage</service>
      <service>DAB (Distributeur automatique de billets)</service>
    </services>
    <prix nom="Gazole" id="1" maj="2026-11-03T08:18:00" valeur="2.417"/>
    <prix nom="E10" id="5" maj="2026-11-03T08:18:00" valeur="2.178"/>
  </pdv>
  <pdv id="2000002" latitude="" longitude="" cp="75001" pop="A">
    <adresse>1 RUE TEST</adresse>
    <ville>PARIS</ville>
    <prix nom="SP98" id="6" maj="2026-11-02T10:00:00" valeur="2.289"/>
  </pdv>
</pdv_liste>
""".encode("iso-8859-1")


def make_zip(tmp_path):
    path = tmp_path / "test.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("PrixCarburants_test.xml", XML)
    return path


def convert(tmp_path, **kwargs):
    stations_path, prices_path = parse.convert_zip(make_zip(tmp_path), tmp_path / "out", **kwargs)
    return pq.read_table(stations_path).to_pylist(), pq.read_table(prices_path).to_pylist()


def test_stations_are_parsed(tmp_path):
    stations, _ = convert(tmp_path)

    first = stations[0]
    assert first["station_id"] == 1000001
    assert first["ville"] == "SAINT-DENIS-LÈS-BOURG"  # encodage ISO-8859-1 bien décodé
    assert first["latitude"] == 46.201  # coordonnées divisées par 100 000
    assert first["automate_24_24"] is True
    assert first["services"] == [
        "Station de gonflage",
        "DAB (Distributeur automatique de billets)",
    ]


def test_missing_fields_become_null(tmp_path):
    stations, _ = convert(tmp_path)

    second = stations[1]
    assert second["latitude"] is None
    assert second["automate_24_24"] is False  # pas de <horaires>
    assert second["services"] == []


def test_prices_are_parsed(tmp_path):
    _, prices = convert(tmp_path)

    assert len(prices) == 3
    assert prices[0] == {
        "station_id": 1000001,
        "carburant": "Gazole",
        "maj": datetime(2026, 11, 3, 8, 18),
        "prix": 2.417,
    }


def test_small_batches_give_same_result(tmp_path):
    _, prices = convert(tmp_path, batch_size=1)

    assert len(prices) == 3


def test_no_tmp_file_left(tmp_path):
    convert(tmp_path)

    assert not list((tmp_path / "out").glob("*.tmp"))
