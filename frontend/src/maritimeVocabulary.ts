export const INDIAN_PORTS = [
  "Paradip", "Haldia", "Kolkata", "Dhamra", "Gopalpur",
  "Visakhapatnam", "Kakinada", "Gangavaram", "Krishnapatnam",
  "Chennai", "Ennore", "Tuticorin", "Kochi", "Mangaluru",
  "New Mangalore", "Mundra", "Kandla", "Pipavav", "Dahej",
  "Hazira", "Mumbai", "JNPT", "Nhava Sheva", "Mormugao",
  "Goa Port", "Karaikal", "Nagapattinam", "Cuddalore"
];

export const VESSEL_TERMS = [
  "trawler", "gillnet", "purse seine", "dhow", "catamaran",
  "mechanized boat", "country boat", "fishing vessel",
  "draft", "freeboard", "squat", "UKC", "ballast"
];

export const MARINE_SAFETY_TERMS = [
  "significant wave height", "swell", "wave period",
  "cyclone", "depression", "trough", "storm surge",
  "Potential Fishing Zone", "PFZ", "EEZ",
  "Marine Protected Area", "no-go zone",
  "mean sea level", "tidal variation", "EOT20"
];

export const ISRO_SPECIFIC = [
  "INCOIS", "MOSDAC", "ISRO", "EOS-06", "OCM-3",
  "chlorophyll", "sea surface temperature", "SST",
  "JalJeev", "SIH", "IBTrACS", "GEBCO"
];

export function getKeyterms(): string[] {
  return [...INDIAN_PORTS, ...VESSEL_TERMS, ...MARINE_SAFETY_TERMS, ...ISRO_SPECIFIC].slice(0, 50);
}

export const CORRECTIONS: Record<string, string> = {
  "para deep": "Paradip",
  "para dip": "Paradip",
  "paradip port": "Paradip",
  "cochin": "Kochi",
  "vizag": "Visakhapatnam",
  "vishakha": "Visakhapatnam",
  "fishing zone": "Potential Fishing Zone",
  "jnpt": "JNPT",
  "haldia port": "Haldia",
  "nhava sheva": "Nhava Sheva",
  "kakinada": "Kakinada",
};

export function applyCorrections(transcript: string): string {
  let result = transcript;
  for (const [wrong, correct] of Object.entries(CORRECTIONS)) {
    const regex = new RegExp(wrong, "gi");
    result = result.replace(regex, correct);
  }
  return result;
}
