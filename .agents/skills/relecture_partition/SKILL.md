---
name: relecture_partition
description: Skill d'analyse harmonique interactive, conçu pour un dialogue fluide avec l'utilisateur, l'inspection ciblée et le nettoyage automatique des annotations.
---

# Relecture de Partition (Mode Interactif)

Ce skill est conçu pour vous guider lors de l'analyse harmonique d'une partition, en gardant un format conversationnel, léger et réactif, plutôt qu'en générant de lourds rapports complets.

## Workflow Interactif
1. **Lecture** : Utilisez `get_score()` pour lire la partition.
2. **Ciblage** : Cherchez en priorité les instructions de l'utilisateur laissées directement dans la partition sous forme de texte (elles apparaîtront comme `%{ @llm : ... %}`). Ne analysez que les mesures concernées par ces requêtes ou par le message de l'utilisateur.
3. **Diagnostic** : Avant toute conclusion, appelez obligatoirement l'outil `check_harmony_rules(start_measure, end_measure)` sur les mesures ciblées pour confirmer les fautes.
4. **Nettoyage** : Une fois votre analyse terminée ou votre correction appliquée, appelez **toujours** `clear_annotations(prefix="@")` pour nettoyer la partition de l'utilisateur de manière "magique".

## Connaissances Harmoniques Essentielles
- 🔴 **Critiques** : Quintes ou octaves parallèles, sensible non résolue (doit monter à la tonique), unissons parallèles.
- 🟠 **Majeures** : Mauvaise doublure (ex: doubler la sensible est interdit), seconde augmentée mélodique, croisement de voix.
- 🟡 **Mineures** : Quintes/octaves directes (cachées) entre voix extrêmes, mauvaise disposition.

*Règle d'or des corrections* : Avant de proposer une solution, vérifiez mentalement qu'elle ne crée pas de nouvelles quintes/octaves parallèles avec l'accord précédent ou le suivant !

## Style de Réponse
- **Soyez concis** : Évitez les synthèses globales ou les tableaux récapitulatifs, sauf demande explicite. 
- **Allez droit au but** : Identifiez la faute directement (ex: *"À la mesure 4, il y a des octaves parallèles entre Alto et Basse."*).
- **Soyez constructif** : Proposez une ou deux options de correction simples et expliquez brièvement leur effet musical.

## Documentation Avancée
Si vous êtes face à un cas très complexe (modulations ambiguës, formes spécifiques), n'hésitez pas à consulter les références situées dans le dossier local du projet : `/Users/lucabankofski/Documents_local/mcp-musescore/knowledge/`.
