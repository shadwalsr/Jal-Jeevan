export interface IndianLanguage {
  displayName: string;
  nativeScript: string;
  bcp47Code: string;
  region: string;
}

export const INDIAN_LANGUAGES: IndianLanguage[] = [
  { displayName: "Odia", nativeScript: "ଓଡ଼ିଆ", bcp47Code: "od-IN", region: "east_coast" },
  { displayName: "Bengali", nativeScript: "বাংলা", bcp47Code: "bn-IN", region: "bengal" },
  { displayName: "Hindi", nativeScript: "हिंदी", bcp47Code: "hi-IN", region: "default" },
  { displayName: "Marathi", nativeScript: "मराठी", bcp47Code: "mr-IN", region: "west_coast" },
  { displayName: "Gujarati", nativeScript: "ગુજરાતી", bcp47Code: "gu-IN", region: "gujarat" },
  { displayName: "Tamil", nativeScript: "தமிழ்", bcp47Code: "ta-IN", region: "south_east" },
  { displayName: "Telugu", nativeScript: "తెలుగు", bcp47Code: "te-IN", region: "andhra" },
  { displayName: "Kannada", nativeScript: "ಕನ್ನಡ", bcp47Code: "kn-IN", region: "karnataka" },
  { displayName: "Malayalam", nativeScript: "മലയാളം", bcp47Code: "ml-IN", region: "kerala" },
  { displayName: "Punjabi", nativeScript: "ਪੰਜਾਬੀ", bcp47Code: "pa-IN", region: "punjab" },
  { displayName: "Assamese", nativeScript: "অসমীয়া", bcp47Code: "as-IN", region: "northeast" },
  { displayName: "Urdu", nativeScript: "اردو", bcp47Code: "ur-IN", region: "urdu_belt" },
  { displayName: "Nepali", nativeScript: "नेपाली", bcp47Code: "ne-IN", region: "northeast" },
  { displayName: "Konkani", nativeScript: "कोंकणी", bcp47Code: "kok-IN", region: "goa" },
  { displayName: "Kashmiri", nativeScript: "کٲشُر", bcp47Code: "ks-IN", region: "kashmir" },
  { displayName: "Sindhi", nativeScript: "سنڌي", bcp47Code: "sd-IN", region: "sindh" },
  { displayName: "Sanskrit", nativeScript: "संस्कृत", bcp47Code: "sa-IN", region: "classical" },
  { displayName: "Santali", nativeScript: "ᱥᱟᱱᱛᱟᱲᱤ", bcp47Code: "sat-IN", region: "jharkhand" },
  { displayName: "Manipuri", nativeScript: "মেইতেই লোন্", bcp47Code: "mni-IN", region: "northeast" },
  { displayName: "Bodo", nativeScript: "बड़ो", bcp47Code: "brx-IN", region: "northeast" },
  { displayName: "Maithili", nativeScript: "मैथिली", bcp47Code: "mai-IN", region: "bihar" },
  { displayName: "Auto-Detect (Any Indian Language)", nativeScript: "Auto", bcp47Code: "unknown", region: "auto" },
  { displayName: "English", nativeScript: "English", bcp47Code: "en-IN", region: "english" },
];

export const COASTAL_PRIORITY_LANGUAGES: IndianLanguage[] = [
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "unknown")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "od-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "bn-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "mr-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "gu-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "ml-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "ta-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "te-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "kn-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "hi-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "pa-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "as-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "ur-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "kok-IN")!,
  INDIAN_LANGUAGES.find((l) => l.bcp47Code === "en-IN")!,
  ...INDIAN_LANGUAGES.filter(
    (l) =>
      ![
        "unknown", "od-IN", "bn-IN", "mr-IN", "gu-IN", "ml-IN",
        "ta-IN", "te-IN", "kn-IN", "hi-IN", "pa-IN", "as-IN",
        "ur-IN", "kok-IN", "en-IN",
      ].includes(l.bcp47Code)
  ),
];
