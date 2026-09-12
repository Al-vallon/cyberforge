# CyberForge

Plateforme personnelle de cyber-range, inspirée du concept Hack The Box.

Le but à terme est d’enchaîner un cycle complet :

CVE récente → analyse → création d’un scénario → génération d’une box → déploiement isolé → pentest → validation automatique → scoring.

Cette version ne construit **pas** encore la plateforme. Elle livre uniquement la première box fonctionnelle, entièrement locale.

## Objectif de cette version

Box 001 est un prototype :

1. lancer une commande ;
2. démarrer une box isolée ;
3. la résoudre ;
4. valider les flags et la configuration ;
5. réinitialiser l’environnement.

Hors périmètre pour l’instant : récupération automatique de CVE, NVD, GitHub Advisory, génération de scénarios, Angular, Spring Boot, PostgreSQL, scoring, authentification, dashboard.

## Concept CVE → Box

Plus tard, une CVE réelle alimentera un scénario et une box dédiée. Box 001 n’utilise **aucune CVE réelle**. La vulnérabilité est volontaire, limitée à ce lab, et n’est pas documentée dans le README public de la box.

## Prérequis

- Fedora Linux
- [Podman](https://podman.io/)
- plugin `podman compose`
- Python 3 (déjà présent sur Fedora, utilisé par les scripts d’opérateur)

Vérification rapide :

```bash
podman --version
podman compose version
systemctl --user start podman.socket
```

Les scripts `deploy.sh` / `destroy.sh` / `reset.sh` démarrent le socket API Podman s’il n’est pas déjà actif (`podman compose` en a besoin).

## Démarrer Box 001

Depuis la racine du dépôt :

```bash
./scripts/deploy.sh
```

Équivalent direct :

```bash
cd boxes/box-001
podman compose up -d --build
```

L’application est ensuite disponible sur [http://127.0.0.1:5000](http://127.0.0.1:5000).

Le port HTTP est bindé **uniquement** sur localhost. La cible Linux n’est pas publiée sur l’hôte.

## Arrêter la box

```bash
./scripts/destroy.sh
```

Équivalent :

```bash
cd boxes/box-001
podman compose down
```

## Réinitialiser la box

```bash
./scripts/reset.sh
```

Cette commande détruit les conteneurs et volumes, reconstruit les images, puis redémarre la box.

## Validation automatique

```bash
./boxes/box-001/validation/validate.sh
```

Le script affiche `[PASS]` / `[FAIL]` pour chaque contrôle, puis :

```text
Box validation: PASS
```

ou

```text
Box validation: FAIL
```

## Sécurité

Ce lab est strictement local.

- aucun scan vers Internet ;
- aucune exploitation d’IP publiques ;
- aucun credential réel ;
- réseau interne isolé (`cyberforge_box001`) ;
- pas de `network_mode: host`.

Si vous voulez **jouer** la box, ne lisez pas `docs/solution.md` ni `boxes/box-001/flags/`.

## Solution

Le walkthrough est volontairement séparé du README public :

- [docs/solution.md](docs/solution.md) — **SPOILER**

## Structure

```text
CyberForge/
├── README.md
├── docs/solution.md
├── boxes/box-001/
└── scripts/
    ├── common.sh
    ├── deploy.sh
    ├── destroy.sh
    └── reset.sh
```

`scripts/common.sh` factorise la détection de Podman/Compose. Ce n’est pas un service supplémentaire, seulement un helper d’opérateur.
