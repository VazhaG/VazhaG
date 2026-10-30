// Every text the page shows, by language (SPEC-0001 REQ-009). Georgian is the main language.

// REQ-002's order; the two gases are separate types (the owner's decision, 2026-10-30).
export const FUELS = ['regular', 'premium', 'super', 'diesel', 'lpg', 'cng'];

export const TEXT = {
  ka: {
    'fuel.regular': 'რეგულარი',
    'fuel.premium': 'პრემიუმი',
    'fuel.super': 'სუპერი',
    'fuel.diesel': 'დიზელი',
    'fuel.lpg': 'თხევადი აირი',
    'fuel.cng': 'ბუნებრივი აირი',
    'status.loading': 'იტვირთება…',
    'status.noPrices': 'ფასები ჯერ არ არის.',
    'status.noFuelPrice': 'ამ საწვავის ფასი არ მოიძებნა.',
    'price.stale': 'შესაძლოა მოძველებულია',
    'best.title': '★ ყველაზე იაფი ახლოს',
    'best.none': '50 კმ-ში ამ საწვავის ახალი ფასით სადგური ვერ მოიძებნა.',
    'best.gasUnknown': 'რომელ სადგურს აქვს აირი, ჯერ ცნობილი არ არის — ფასები ქვემოთ, ცხრილშია.',
    'unit.km': 'კმ',
    'go.google': 'Google Maps',
    'go.waze': 'Waze',
    'station.noPrice': 'ფასი ჯერ არ არის.',
    'city.ask': 'მდებარეობა უცნობია — აირჩიე ქალაქი:',
  },
};

let lang = 'ka';

export function t(key) {
  return TEXT[lang][key] ?? key;
}
