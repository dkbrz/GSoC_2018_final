# GSoC 2018

## Bilingual dictionary enrichment via graph completion
**Organization**: Apertium

This tool allows bilingual dictionary enrichment using graph built from bilingual dictionaries. For exmaple, you want to translate église from French to Russian but you don't have this entry. You have: FRA_église - CAT_església, FRA_église - SPA_iglesia, CAT_església - ENG_church, SPA_iglesia - ENG_church, ENG_churh - RUS_церковь

Conneting these edges you get two paths FRA_église - CAT_església - ENG_church - RUS_церковь and FRA_église - SPA_iglesia - ENG_church - RUS_церковь.

## Links:
- [Instruction](https://github.com/dkbrz/GSoC_2018_final/wiki/Instruction)
- [Apertium Wiki Page](http://wiki.apertium.org/wiki/Bilingual_dictionary_enrichment_via_graph_completion)
- [GSoC ideas for this project](http://wiki.apertium.org/wiki/Ideas_for_Google_Summer_of_Code/Bilingual_dictionary_enrichment_via_graph_completion)