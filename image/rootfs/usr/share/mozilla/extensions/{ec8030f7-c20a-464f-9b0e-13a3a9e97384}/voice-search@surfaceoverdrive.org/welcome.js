// The page shown once after installing from addons.mozilla.org, in Italian or English.
const it = (navigator.language || "").toLowerCase().startsWith("it");
const steps = it ? [
  "Tocca il <b>microfono</b> accanto alla barra degli indirizzi: si apre direttamente la ricerca vocale di Google.",
  "La prima volta Firefox chiede il permesso del microfono per google.com: scegli <b>Consenti</b> e spunta <b>Ricorda questa decisione</b>. Da lì in poi vedi solo la schermata di ascolto, poi i risultati.",
  "Per usarla anche nelle finestre private: menu ☰ → <b>Componenti aggiuntivi e temi</b> → Voice Search for Google → <b>Esegui in finestre anonime: Consenti</b>.",
  "Non vedi il microfono? Menu ☰ → <b>Altri strumenti</b> → <b>Personalizza barra degli strumenti</b> e trascinalo dove preferisci."
] : [
  "Tap the <b>microphone</b> beside the address bar: Google's voice search opens straight away.",
  "The first time, Firefox asks to allow the microphone for google.com: choose <b>Allow</b> and tick <b>Remember this decision</b>. From then on you only see the listening screen, then the results.",
  "To use it in private windows too: menu ☰ → <b>Add-ons and themes</b> → Voice Search for Google → <b>Run in Private Windows: Allow</b>.",
  "No microphone in sight? Menu ☰ → <b>More tools</b> → <b>Customize toolbar</b>, and drag it where you like."
];
const list = document.getElementById("steps");
for (const text of steps) {
  const li = document.createElement("li");
  for (const part of text.split(/(<b>.*?<\/b>)/)) {     // plain text and <b>bold</b>, no HTML parsing
    if (part.startsWith("<b>")) {
      const b = document.createElement("b");
      b.textContent = part.slice(3, -4);
      li.append(b);
    } else if (part) {
      li.append(part);
    }
  }
  list.append(li);
}
document.getElementById("privacy").textContent = it
  ? "Privacy: l'estensione non raccoglie né invia dati. Parla solo con google.com, come la ricerca vocale sul sito di Google; non è affiliata a Google."
  : "Privacy: the extension collects and sends no data. It only talks to google.com, like voice search on Google's own site; it is not affiliated with Google.";
