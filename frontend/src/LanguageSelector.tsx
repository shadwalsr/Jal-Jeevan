import { useEffect, useRef, useState } from "react";
import { useLanguage } from "./i18n/LanguageContext";

export function LanguageSelector() {
  const { language, setLanguage, languages, t } = useLanguage();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  return (
    <div className="lang-selector" ref={containerRef}>
      <button
        type="button"
        className={`lang-selector__btn ${isOpen ? "active" : ""}`}
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={t("select_language")}
        title={`${t("select_language")} — ${language.nativeName}`}
      >
        <span className="lang-selector__icon" aria-hidden="true">🌐</span>
        <span className="lang-selector__current-name">{language.nativeName}</span>
        <span className="lang-selector__chevron" aria-hidden="true">▾</span>
      </button>

      {isOpen && (
        <div className="lang-selector__dropdown surface" role="listbox" aria-label={t("select_language")}>
          <div className="lang-selector__header">
            <span>{t("select_language")}</span>
          </div>
          <div className="lang-selector__list">
            {languages.map((l) => {
              const isSelected = l.code === language.code;
              return (
                <button
                  key={l.code}
                  type="button"
                  className={`lang-selector__item ${isSelected ? "selected" : ""}`}
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => {
                    setLanguage(l.code);
                    setIsOpen(false);
                  }}
                >
                  <div className="lang-selector__item-texts">
                    <span className="lang-selector__item-native">{l.nativeName}</span>
                    <span className="lang-selector__item-meta">
                      {l.name} • {l.region}
                    </span>
                  </div>
                  {isSelected && <span className="lang-selector__checkmark" aria-hidden="true">✓</span>}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
