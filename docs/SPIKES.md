# Spike: cosa verificare sul tablet prima di scrivere codice

Ogni spike ha una domanda, un metodo, un criterio di successo e cosa cambia nell'architettura a seconda del risultato.
Servono accesso al Surface (SSH o terminale diretto) e la sua installazione aggiornata.

## S1: l'NFC funziona senza patch al kernel?
- **Domanda**: il driver stock `nxp-nci_i2c` si può legare al dispositivo ACPI `NXP3001:00` senza compilare nulla?
- **Metodo**: vedere se il bus i2c espone `driver_override` per il dispositivo; provare `bind` del driver stock; in alternativa leggere `/sys/bus/i2c/devices/i2c-NXP3001:00`.
  Misurare quanto spesso compaiono letture NACK senza la patch di retry.
- **Successo**: tag letti con il driver stock e latenza simile a quella della vecchia repo.
- **Se sì**: l'NFC esce dai moduli da compilare (restano solo camera e volume). **Se no**: modulo firmato in CI, con la patch di retry da proporre a monte.

## S2: quali patch kernel servono ancora su 7.2.x stock?
- **Domanda**: dopo i rilasci recenti, quali delle 9 patch ai driver sono ancora necessarie?
- **Metodo**: per ognuna, leggere il sorgente del kernel Fedora in uso e provare il comportamento con il modulo stock (`ov8865`: modo stale, pixel rate, gain, 800x600; `ov5693`: 30 fps; `intel_hid`).
- **Successo**: elenco minimo di patch con motivazione e misura.
- **Esito**: ogni patch non necessaria esce dal progetto.

## S3: valore marginale di ogni patch libcamera
- **Domanda**: quali delle 12 patch cambiano davvero la qualità, e di quanto?
- **Metodo**: ricostruire libcamera aggiungendo una patch alla volta, con gli strumenti di misura della vecchia repo (nitidezza dell'AF, stabilità della luminanza, crash nello stress test).
- **Successo**: tabella patch → effetto misurato → livello (1, 2, 3).

## S4: calibrazione propria
- **Domanda**: da misure nostre si ottiene lens shading e black level di qualità pari o migliore delle tabelle Microsoft?
- **Metodo**: acquisire RAW dalla CIO2 (campo bianco e obiettivo coperto), stimare le griglie, applicarle e misurare luminanza e rapporti R/G e B/G al centro e ai bordi. Confronto privato con il vecchio tuning.
- **Successo**: scarto del centro e dei bordi pari o minore della vecchia repo (luminanza: bordo 1,00 del centro ±3%; R/G e B/G entro ±2%).
- **Esito**: se non basta si cerca un metodo migliore; le tabelle Microsoft non entrano comunque.

## S5: audio
- **Domanda**: il volume basso e il microfono troppo sensibile si risolvono a livello ALSA/UCM/WirePlumber o serve la catena filter-chain?
- **Metodo**: esaminare `amixer contents`, il profilo ALSA in uso e i limiti del codec; provare regole WirePlumber sui controlli del mixer.
- **Successo**: volume udibile senza distorsione e microfono con guadagno ragionevole senza un dispositivo virtuale aggiuntivo.

## S6: ponte tra KCM e `forged`
- **Domanda**: qual è il modo minimo per far parlare una pagina di Impostazioni di Sistema con un servizio D-Bus?
- **Metodo**: provare un KCM minimo con plugin C++ e verificare cosa è possibile in QML puro. Controllare anche come far comparire una voce in Impostazioni.
- **Successo**: una pagina visibile in Impostazioni che mostra lo stato letto da D-Bus.
