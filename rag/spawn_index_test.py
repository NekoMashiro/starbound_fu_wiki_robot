"""星球生成表：解析 Cargo，并把生态挂到星球上。"""

import html
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from spawn_index import (
    build_found_on,
    build_spawn_index,
    biome_appearances,
    collect_biome_plants,
    planet_biome_tables,
    format_location_brief,
    iter_cargo_stores,
    parse_output_rates,
    wants_location_query,
)

CARGO = """
{{#cargo_store:_table = planet
|id=lightless
|name=Lightless
|minTier=5
|maxTier=6
}} {{#cargo_store:_table = planet
|id=desert
|name=Desert
|minTier=2
|maxTier=2
}} {{#cargo_store:_table = region
|id=lightless
|biome=lightless
}} {{#cargo_store:_table = region
|id=desert
|biome=desert
}} {{#cargo_store:_table = layer
|planet=lightless
|layer=underground1
|primaryRegion=lightless
|secondaryRegions=
}} {{#cargo_store:_table = layer
|planet=desert
|layer=surface
|primaryRegion=desert
|secondaryRegions=lightless
}} {{#cargo_store:_table = biome
|id=lightless
|name=Lightless
}} {{#cargo_store:_table = recipe
|station=Biome objects
|inputs=biome:lightless
|outputs=weaponupgradeanvil2
|wikitext={{Recipe|inputs=
* [[Lightless|Biome: Lightless]] ''(underground)''
|outputs=
* [[Cosmic Crucible]] '''0.94%'''
}}
}} {{#cargo_store:_table = recipe
|station=Biome monsters
|inputs=biome:desert
|outputs=monster:snaunt,monster:electricsnaunt
|wikitext={{Recipe|inputs=
* [[Desert|Biome: Desert]] ''(monsters)''
|outputs=
Any 1 of the following:
<div class="recipe-group">
* [[Snaunt]] '''99%'''
* [[Electric Snaunt]] '''1%'''
</div> '''40%'''
}}
}} {{#cargo_store:_table = recipe
|station=Biome trees
|inputs=biome:desert
|outputs=stem:weeping,foliage:apple
|wikitext={{Recipe|inputs=
* [[Desert|Biome: Desert]] ''(surface)''
|outputs=
* [[Template:Modular tree part/Stem/weeping|Stem: weeping (Weeping)]]
* [[Template:Modular tree part/Foliage/apple|Foliage: apple (Apple)]]
}}
}} {{#cargo_store:_table = recipe
|station=Biome objects
|inputs=biome:desert
|outputs=toxictopseed
|wikitext={{Recipe|inputs=
* [[Desert|Biome: Desert]] ''(surface)''
|outputs=
* [[Toxictop Seed]] '''100%'''
}}
}} {{#cargo_store:_table = recipe
|station=Wooden Workbench
|inputs=wood
|outputs=stick
|wikitext={{Recipe|inputs=
* [[Wood]]
|outputs=
* [[Stick]]
}}
}}
"""

XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">
  <page>
    <title>Template:Cargo/test</title>
    <revision><text>old</text></revision>
    <revision><text xml:space="preserve">{html.escape(CARGO)}</text></revision>
  </page>
</mediawiki>
"""


class SpawnParseTest(unittest.TestCase):
    def test_location_question(self):
        self.assertTrue(wants_location_query('宇宙铁砧在哪种星球，生成率多少'))
        self.assertTrue(wants_location_query('钨矿在哪挖'))
        self.assertFalse(wants_location_query('钨矿怎么熔炼'))

    def test_group_rate(self):
        rates = parse_output_rates(
            "|outputs=\n"
            "<div class=\"recipe-group\">\n"
            "* [[Snaunt]] '''99%'''\n"
            "* [[Electric Snaunt]] '''1%'''\n"
            "</div> '''40%'''\n"
        )
        self.assertEqual(rates[0]['rate'], 99)
        self.assertEqual(rates[0]['group_rate'], 40)
        self.assertEqual(rates[1]['rate'], 1)
        self.assertEqual(rates[1]['group_rate'], 40)

    def test_skips_crafting_recipe(self):
        tables = [table for table, _fields in iter_cargo_stores(CARGO)]
        self.assertIn('recipe', tables)
        self.assertEqual(tables.count('planet'), 2)

    def test_build_links_object_to_planet(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / 'wiki.xml'
            xml.write_text(XML, encoding='utf-8')
            biome_dir = Path(tmp) / 'biome'
            biome_dir.mkdir()
            (biome_dir / 'lightless.json').write_text(
                '{"friendly_name_zh": "无光星球", "friendly_name": "Lightless Sphere"}',
                encoding='utf-8',
            )
            item_dir = Path(tmp) / 'item'
            item_dir.mkdir()
            (item_dir / 'tungstenore.json').write_text('{}', encoding='utf-8')
            ores = Path(tmp) / 'biome_ores.json'
            ores.write_text(
                '{"desert": [{"ore": "tungsten", "weight": 0.2}, {"ore": "tungsten", "weight": 0.6}]}',
                encoding='utf-8',
            )
            index = build_spawn_index(xml, biome_dir, ores, item_dir)

        brief = format_location_brief(index, [{
            'entity_id': 'weaponupgradeanvil2',
            'name_zh': '宇宙铁砧',
            'name_en': 'Cosmic Crucible',
        }])
        self.assertIn('宇宙铁砧(Cosmic Crucible)', brief)
        self.assertIn('生成率 0.94%', brief)
        self.assertIn('无光星球(Lightless)', brief)
        self.assertIn('Lightless', brief)
        self.assertIn('地下浅层', brief)
        self.assertIn('次级生态', brief)

        monster = format_location_brief(index, [{
            'entity_id': 'snaunt',
            'name_en': 'Snaunt',
        }])
        self.assertIn('生成率 99%', monster)
        self.assertIn('40%', monster)
        self.assertIn('Desert', monster)

        ore = format_location_brief(index, [{
            'entity_id': 'tungstenore',
            'name_zh': '钨矿',
            'name_en': 'Tungsten Ore',
        }])
        self.assertIn('权重 0.6', ore)
        self.assertIn('不是生成率', ore)
        self.assertIn('Desert', ore)
        self.assertNotIn('0.2', ore)

        found = build_found_on(index, 'weaponupgradeanvil2')
        self.assertEqual(found['places'][0]['rate'], '0.94%')
        self.assertIn('无光星球(Lightless)', found['places'][0]['planets'])
        ore_found = build_found_on(index, 'tungstenore')
        self.assertEqual(ore_found['ore_planets'][0]['surface_weight'], 0.6)
        self.assertIn('Desert', ore_found['ore_planets'][0]['planets'])
        self.assertLess(len(json.dumps(ore_found, ensure_ascii=False)), 800)

        plants = collect_biome_plants(index, {
            'toxictopseed': {'name': '毒果种子(Toxictop Seed)', 'category': 'seed'},
        })
        desert = plants['desert']
        self.assertIn('Weeping', desert['trees'])
        self.assertIn('Apple', desert['trees'])
        self.assertEqual(desert['ground'][0]['id'], 'toxictopseed')
        self.assertEqual(desert['ground'][0]['rate'], '100%')
        self.assertIn('Desert', desert['planets'])

        places = biome_appearances(index)
        self.assertEqual(places['desert'], [
            {'planet': 'Desert', 'where': '地表', 'role': '主生态'},
        ])
        self.assertEqual(places['lightless'], [
            {'planet': '无光星球(Lightless)', 'where': '地下浅层', 'role': '主生态'},
            {'planet': 'Desert', 'where': '地表', 'role': '次级生态'},
        ])
        layers = planet_biome_tables(index)
        self.assertEqual(layers['desert'], [{
            'where': '地表',
            '主生态': ['Desert'],
            '次级生态': ['无光星球(Lightless)'],
        }])
        self.assertEqual(layers['lightless'][0]['主生态'], ['无光星球(Lightless)'])


if __name__ == '__main__':
    unittest.main()
