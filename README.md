# CAD90Pro — Calcul & Ferraillage des Ponts Cadres en Béton Armé

Application d'ingénierie des ouvrages d'art hydrauliques et routiers (dalots simples, doubles et triples).

## Fonctionnalités
- **Saisie interactive** : Géométrie, remblais multiples, surcharges routières A(L), Bc, Bt, Br, sol.
- **Aperçu vectoriel temps réel** : Coupe transversale du dalot avec cotes.
- **Moteurs de calcul patrimoniaux 64-bit** : `CASIMPLE_WIN64`, `CADOUBLE_WIN64`, `CATRIPLE_WIN64`.
- **Restitution structurée** : Moments fléchissants, armatures principales, étriers.
- **Exports professionnels** :
  - Note de calcul PDF (A4 vectorielle pure).
  - Bordereau quantitatif Excel (BQ) avec formules et métrés de ferraillage.

## Déploiement Cloud sur Render (Docker)
Cette application est pré-configurée avec un `Dockerfile` intégrant **Wine64** pour exécuter les moteurs sous Linux.

1. Créer un **Web Service** sur [Render.com](https://dashboard.render.com).
2. Lier ce dépôt GitHub (`adnnae/CAD90`).
3. Choisir l'environnement **Docker**.
4. Type d'instance : **Free**.
5. Render démarre automatiquement Streamlit sur le port exposé.
