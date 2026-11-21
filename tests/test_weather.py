# -*- coding: utf-8 -*-

from __future__ import annotations

import unittest

from gyhd.weather import Temperature, parse_open_meteo, parse_vvhan


class WeatherParseTest(unittest.TestCase):
    def test_parse_normal(self) -> None:
        payload = {
            "daily": {
                "temperature_2m_min": [15.4],
                "temperature_2m_max": [24.6],
            }
        }
        temperature = parse_open_meteo(payload)
        self.assertEqual(temperature, Temperature(low=15, high=25))
        self.assertEqual(temperature.text, "15℃~25℃")

    def test_parse_reversed(self) -> None:
        payload = {
            "daily": {
                "temperature_2m_min": [26.0],
                "temperature_2m_max": [18.0],
            }
        }
        temperature = parse_open_meteo(payload)
        self.assertEqual(temperature, Temperature(low=18, high=26))

    def test_missing_daily(self) -> None:
        self.assertIsNone(parse_open_meteo({}))
        self.assertIsNone(parse_open_meteo({"daily": {}}))
        self.assertIsNone(
            parse_open_meteo({"daily": {"temperature_2m_min": []}})
        )

    def test_bad_values(self) -> None:
        self.assertIsNone(
            parse_open_meteo(
                {
                    "daily": {
                        "temperature_2m_min": ["bad"],
                        "temperature_2m_max": [20],
                    }
                }
            )
        )
        self.assertIsNone(
            parse_open_meteo(
                {
                    "daily": {
                        "temperature_2m_min": [-999],
                        "temperature_2m_max": [20],
                    }
                }
            )
        )

    def test_parse_vvhan(self) -> None:
        self.assertEqual(
            parse_vvhan({"data": {"low": "15℃", "high": "25℃"}}),
            Temperature(low=15, high=25),
        )
        self.assertEqual(
            parse_vvhan({"low": "15°C", "high": "25°C"}),
            Temperature(low=15, high=25),
        )
        self.assertIsNone(parse_vvhan({"data": {"low": "无"}}))


if __name__ == "__main__":
    unittest.main()
