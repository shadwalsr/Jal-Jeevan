import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  SUPPORTED_LANGUAGES,
  TRANSLATIONS,
  type SupportedLanguage,
  type TranslationKey,
} from "./translations";

interface LanguageContextType {
  language: SupportedLanguage;
  setLanguage: (code: string) => void;
  t: (key: TranslationKey, params?: Record<string, string | number>) => string;
  languages: SupportedLanguage[];
}

const STORAGE_KEY = "jaljeev_language_preference";

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [langCode, setLangCode] = useState<string>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && SUPPORTED_LANGUAGES.some((l) => l.code === saved)) {
        return saved;
      }
    } catch {
      // ignore
    }
    return "en";
  });

  const currentLanguage =
    SUPPORTED_LANGUAGES.find((l) => l.code === langCode) || SUPPORTED_LANGUAGES[0];

  const handleSetLanguage = (code: string) => {
    if (SUPPORTED_LANGUAGES.some((l) => l.code === code)) {
      setLangCode(code);
      try {
        localStorage.setItem(STORAGE_KEY, code);
      } catch {
        // ignore
      }
    }
  };

  useEffect(() => {
    // Set document lang attribute
    document.documentElement.lang = currentLanguage.code;
  }, [currentLanguage]);

  const t = (key: TranslationKey, params?: Record<string, string | number>): string => {
    const dict = TRANSLATIONS[currentLanguage.code] || TRANSLATIONS.en;
    let text = dict[key] || TRANSLATIONS.en[key] || key;

    if (params) {
      for (const [paramKey, paramVal] of Object.entries(params)) {
        text = text.replace(new RegExp(`{${paramKey}}`, "g"), String(paramVal));
      }
    }
    return text;
  };

  return (
    <LanguageContext.Provider
      value={{
        language: currentLanguage,
        setLanguage: handleSetLanguage,
        t,
        languages: SUPPORTED_LANGUAGES,
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextType {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used within a LanguageProvider");
  }
  return context;
}
