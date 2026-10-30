// Every text the page writes, in both languages (SPEC-0001 REQ-009). Georgian is the main language. What the
// companies' sites write — fuel and station names, addresses — is shown as they publish it.

// REQ-002's order; the two gases are separate types (the owner's decision, 2026-10-30).
export const FUELS = ['regular', 'premium', 'super', 'diesel', 'lpg', 'cng'];
export const LANGS = ['ka', 'en'];

export const TEXT = {
  ka: {
    'title.page': 'საწვავის ფასები საქართველოში',
    'title.h1': '⛽ საწვავის ფასები',
    'fuel.legend': 'საწვავის ტიპი',
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
    'table.title': 'ფასები კომპანიების მიხედვით',
    'table.company': 'კომპანია',
    'table.price': 'ფასი',
    'table.time': 'შემოწმდა',
    'time.source': 'კომპანიის თარიღი',
    'note.times': 'დრო გვიჩვენებს, როდის წაიკითხა ჩვენმა პროგრამამ ფასი კომპანიის საიტზე: საიტები ფასის თარიღს არ აქვეყნებენ.',
    'note.source': 'ფასები მოდის კომპანიების ოფიციალური საიტებიდან და სადგურზე შეიძლება განსხვავდებოდეს.',
    'note.standard': 'ფასი სტანდარტულია; თვითმომსახურებისა და ბარათის ფასი შეიძლება დაბალი იყოს.',
    'note.tiles':
      'რუკის სურათები OpenStreetMap-ის სერვერიდან იტვირთება იმ არეალისთვის, რომელსაც ეკრანი აჩვენებს; '
      + 'შენი ზუსტი მდებარეობა არსად იგზავნება.',
    'note.cities': 'ქალაქების კოორდინატები:',
    'lang.group': 'ენა',
  },
  en: {
    'title.page': 'Fuel prices in Georgia',
    'title.h1': '⛽ Fuel prices',
    'fuel.legend': 'Fuel type',
    'fuel.regular': 'Regular',
    'fuel.premium': 'Premium',
    'fuel.super': 'Super',
    'fuel.diesel': 'Diesel',
    'fuel.lpg': 'LPG',
    'fuel.cng': 'CNG',
    'status.loading': 'Loading…',
    'status.noPrices': 'No prices yet.',
    'status.noFuelPrice': 'No price found for this fuel.',
    'price.stale': 'may be out of date',
    'best.title': '★ Cheapest nearby',
    'best.none': 'No station with a recent price for this fuel within 50 km.',
    'best.gasUnknown': 'Which stations sell this gas is not known yet — see the prices in the table below.',
    'unit.km': 'km',
    'go.google': 'Google Maps',
    'go.waze': 'Waze',
    'station.noPrice': 'No price yet.',
    'city.ask': 'Location unknown — choose a city:',
    'table.title': 'Prices by company',
    'table.company': 'Company',
    'table.price': 'Price',
    'table.time': 'Checked',
    'time.source': "the company's date",
    'note.times': "The time is when our program read the price on the company's site: the sites publish no date.",
    'note.source': "Prices come from the companies' official websites and may differ at the station.",
    'note.standard': 'Standard prices; self-service and card prices may be lower.',
    'note.tiles':
      'Map images load from the OpenStreetMap server for the area on the screen; your exact location is never sent.',
    'note.cities': 'City coordinates:',
    'lang.group': 'Language',
  },
};

let current = 'ka';

export function setLang(lang) {
  if (LANGS.includes(lang)) current = lang;
}

export function lang() {
  return current;
}

export function t(key) {
  return TEXT[current][key] ?? TEXT.ka[key] ?? key;
}
