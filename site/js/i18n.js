// Every text the page shows, by language (SPEC-0001 REQ-009). Georgian is the main language.

export const FUELS = ['regular', 'premium', 'super', 'diesel', 'gas'];

export const TEXT = {
  ka: {
    'fuel.regular': 'რეგულარი',
    'fuel.premium': 'პრემიუმი',
    'fuel.super': 'სუპერი',
    'fuel.diesel': 'დიზელი',
    'fuel.gas': 'გაზი',
    'status.loading': 'იტვირთება…',
    'status.noPrices': 'ფასები ჯერ არ არის.',
    'status.noFuelPrice': 'ამ საწვავის ფასი არ მოიძებნა.',
    'price.stale': 'შესაძლოა მოძველებულია',
  },
};

let lang = 'ka';

export function t(key) {
  return TEXT[lang][key] ?? key;
}
