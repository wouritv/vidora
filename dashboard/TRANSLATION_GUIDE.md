# Guide Traduction UI (i18n) - Vireel

## Objectif
Le frontend supporte les traductions via fichiers JSON.
La langue est choisie automatiquement selon `navigator.language`.
Langues supportees actuellement : `en`, `fr`.
Fallback : `en`.

---

## Structure

- `src/state/LanguageContext.jsx`
- `src/locales/en/common.json`
- `src/locales/fr/common.json`

---

## Comment ca marche

`LanguageProvider` :
- detecte la langue navigateur (`fr-FR` -> `fr`)
- verifie si elle est supportee
- fallback `en` si non supportee
- expose `t(key, fallback, vars)` via `useTranslation()`

Exemple :
```jsx
const { t } = useTranslation();
<h1>{t("app.reelGenerator", "Reel generation")}</h1>
```

Interpolation :
```jsx
t("reels.insufficientForShare", "Insufficient credits: {{required}}", { required: 10 })
```

---

## Ajouter une nouvelle langue

Exemple pour espagnol (`es`) :

1. Creer le dossier/fichier :
- `src/locales/es/common.json`

2. Ajouter le dictionnaire dans `LanguageContext.jsx` :
- importer `esCommon`
- ajouter `es` dans `SUPPORTED_LANGUAGES`
- ajouter `es: esCommon` dans `DICTIONARIES`

3. Remplir toutes les cles deja existantes dans `en/common.json`.

---

## Ajouter un nouveau texte

1. Ajouter une cle dans `en/common.json` et `fr/common.json` :
```json
{
  "mySection": {
    "newLabel": "My text"
  }
}
```

2. Utiliser dans le composant :
```jsx
t("mySection.newLabel", "My text")
```

Toujours mettre un fallback lisible en 2e argument.

---

## Utilisation dans l'UI

Dans un composant React :
```jsx
import { useTranslation } from "../state/LanguageContext";

function MyComponent() {
  const { t } = useTranslation();

  return (
    <button>{t("common.cancel", "Cancel")}</button>
  );
}
```

---

## Bonnes pratiques

- Aucun texte user-facing en dur.
- Toujours passer par `t(...)`.
- Garder les memes cles entre toutes les langues.
- Utiliser des namespaces (`app.*`, `settings.*`, `reels.*`, etc.).
- Ajouter les nouveaux textes d'abord dans `en`, puis dans `fr`.

