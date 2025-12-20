# dji-agras-assistant

Tecnical Assistant Agents for DJI Agras T40 and T50

### Testing and Helper Scripts

Test Domain Knowledge Database:
```bash
python3 -m domain_knowledge.dk_database_testing
```

Rank components by risk:
```bash
# T40
python3 -m domain_knowledge.dk_analysis rank_comp_risk domain_knowledge/T40_dka T40_comp_risk_analysis.json
# T50
python3 -m domain_knowledge.dk_analysis rank_comp_risk domain_knowledge/T50_dka T50_comp_risk_analysis.json
```
