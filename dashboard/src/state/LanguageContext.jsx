import { createContext, useContext, useMemo } from "react";
import enCommon from "../locales/en/common.json";
import frCommon from "../locales/fr/common.json";

const SUPPORTED_LANGUAGES = ["en", "fr"];
const DEFAULT_LANGUAGE = "en";

const DICTIONARIES = {
    en: enCommon,
    fr: frCommon,
};

const LanguageContext = createContext(null);

function detectBrowserLanguage() {
    const raw = (globalThis?.navigator?.language || "").toLowerCase();
    const short = raw.split("-")[0];
    if (SUPPORTED_LANGUAGES.includes(short)) return short;
    return DEFAULT_LANGUAGE;
}

function getByPath(obj, path) {
    if (!obj || !path) return undefined;
    return String(path)
        .split(".")
        .reduce((acc, key) => (acc && Object.prototype.hasOwnProperty.call(acc, key) ? acc[key] : undefined), obj);
}

function interpolate(template, vars = {}) {
    if (typeof template !== "string") return template;
    return template.replace(/\{\{\s*(\w+)\s*\}\}/g, (_match, key) => {
        if (!Object.prototype.hasOwnProperty.call(vars, key)) return "";
        const value = vars[key];
        return value === null || value === undefined ? "" : String(value);
    });
}

export function LanguageProvider({ children }) {
    const language = detectBrowserLanguage();
    const dictionary = DICTIONARIES[language] || DICTIONARIES[DEFAULT_LANGUAGE];

    const value = useMemo(
        () => ({
            language,
            supportedLanguages: SUPPORTED_LANGUAGES,
            t: (key, fallback = key, vars = {}) => {
                const found = getByPath(dictionary, key);
                const base = typeof found === "string" ? found : fallback;
                return interpolate(base, vars);
            },
        }),
        [language, dictionary]
    );

    return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useTranslation() {
    const ctx = useContext(LanguageContext);
    if (!ctx) {
        throw new Error("useTranslation must be used inside LanguageProvider");
    }
    return ctx;
}

