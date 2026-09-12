# CyberForge Box 001

Box Linux volontairement vulnérable, entièrement locale.

| Champ        | Valeur              |
|--------------|---------------------|
| Nom          | CyberForge Box 001  |
| Slug         | `box-001`           |
| Version      | 1.0                 |
| Difficulté   | Easy                |
| CVE          | aucune              |

## Objectifs

- initial access
- user flag
- privilege escalation
- root flag

## Démarrage

Depuis la racine du dépôt :

```bash
./scripts/deploy.sh
```

Application web : [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Arrêt / reset / validation

```bash
./scripts/destroy.sh
./scripts/reset.sh
./boxes/box-001/validation/validate.sh
```

## Périmètre

Le joueur n’a accès qu’au service HTTP publié sur `127.0.0.1:5000`.

La machine cible n’écoute pas sur l’hôte. Le réseau interne s’appelle `cyberforge_box001`.

Ce README ne contient pas la solution. Le walkthrough interne est dans `docs/solution.md` à la racine du dépôt.
