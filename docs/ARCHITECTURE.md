# Surface Forge: architettura (bozza v0, 2026-10-06)

Progetto personale per un Surface Go 1824 (Wi-Fi, 8 GB, NVMe) con Fedora Kinoite 44, poi 45, Secure Boot attivo.
Non è pensato per altri modelli né per altri utenti. Ogni scelta è marcata **[DECISO]** oppure **[DA VERIFICARE]**
(in quel caso c'è uno spike in `docs/SPIKES.md` che la conferma o la smentisce sul dispositivo).

## 1. Obiettivo

Su una Kinoite appena installata e aggiornata, un solo comando porta il tablet a un sistema in cui fotocamere, NFC, tasti volume,
penna, tastiera e audio funzionano, e **continua a funzionare dopo gli aggiornamenti senza che l'utente ricompili nulla**.
Se qualcosa si rompe, il sistema lo nota, lo dice e propone la riparazione.

Vincoli:
- **Nessun dato Microsoft** nel progetto (né tabelle di calibrazione né derivati). La calibrazione delle camere si ricava da misure nostre.
- Nessuna dipendenza dal clone locale della repo: tutto quello che serve a runtime viene dall'immagine di sistema.
- Il tablet **non compila niente**. Si compila in CI.
- Degradare con grazia: se un fix manca, il sistema si comporta come lo stock. Mai un boot rotto.
- Il progetto serve a me, quindi niente compromessi per la portabilità. La qualità però deve essere quella di un progetto serio.

## 2. Principi

1. **Ogni fix è una dichiarazione e una verifica.** Non una sequenza di comandi.
2. **Tutto quello che arriva dalla vecchia repo è un'ipotesi**: si rimisura prima di fidarsi (vedi SPIKES).
3. **Meno patch sono meglio.** Per ognuna: serve ancora? è un bug upstream? si può mandare a monte? Una patch accettata a monte è manutenzione che sparisce.
4. **Si distingue la correttezza dalle funzioni.** Le patch che correggono bug vengono prima di quelle che aggiungono controlli.
5. **Il sistema è osservabile.** Ogni componente scrive nel journal con un identificatore stabile e ha un comando di stato.

## 3. Mappa dei problemi

| Problema | Soluzione | Dove vive | Stato |
|---|---|---|---|
| Camera posteriore: strisce verdi (modo del sensore rimasto vecchio) | Patch al driver `ov8865` (già proposta a linux-surface) | modulo kernel | consolidata |
| Esposizione sbagliata di 4× sulla posteriore (pixel rate), gain a gradini, modo 800x600 inutilizzabile | Patch al driver `ov8865` | modulo kernel | da rivalutare uno per uno (S2) |
| Anteriore: frame rate oltre il limite del ricevitore | Patch a `ov5693` | modulo kernel | da verificare se serve ancora (S2) |
| NFC: `NXP3001` non riconosciuto, letture NACK che bloccano il chip | Id aggiunto + retry; oppure binding del driver stock | modulo oppure regola udev | **S1** |
| Tasti volume non si ripetono | Patch a `intel_hid` | modulo kernel | consolidata |
| Crash di WirePlumber (`std::clamp`, frame in volo) | Patch a libcamera (bug upstream) | libcamera | consolidata, da proporre a monte |
| Messa a fuoco instabile, AE/AGC, sensor delays, black level, flip della posteriore | Patch a libcamera (livello 1) | libcamera | consolidata, da rimisurare (S3) |
| Vignettatura e dominante di colore | Calibrazione **propria** (lens shading e black level da misure) | `/var/lib/surface-forge/calibration/` | **S4** |
| Controlli live (gamma, saturazione, denoise...) | Livello 3: rimandato | libcamera + pannello | dopo M5 |
| Batteria penna sempre 0% | Programma HID-BPF | immagine | consolidata |
| Trackpad della tastiera a volte assente | Regola udev e unità di recupero | immagine | consolidata |
| Audio basso, microfono troppo sensibile | Catena filter-chain di PipeWire (come Asahi) oppure regole ALSA/WirePlumber | immagine | **S5** |

Livelli delle patch libcamera: **1** correttezza (crash, AF, AGC, black level, flip, delays), **2** qualità (lens shading con tabelle nostre, tone curve),
**3** funzioni (profilo live, denoise temporale, controlli del pannello). Si porta in produzione un livello alla volta.

## 4. Distribuzione: immagine bootc personalizzata **[DECISO]**

Si parte da `quay.io/fedora-ostree-desktops/kinoite:44` (e `:45` appena c'è la base stabile) e si aggiunge solo quello che serve.

Perché non script sul tablet o layering:
- kernel e moduli viaggiano insieme: **non può esistere un kernel nuovo senza i moduli giusti**. Se la build fallisce, l'immagine non esce;
- i moduli finiscono in `/usr/lib/modules/<kver>/updates/` con `depmod`, che il sistema preferisce a quelli stock. Quindi niente regole `install ... insmod`, niente `/var/lib/local-kmods`, niente marker, niente servizio dedicato per caricare l'NFC;
- libcamera si sostituisce con un pacchetto ricostruito, senza `/usr/local` e senza `LD_LIBRARY_PATH`;
- rollback e aggiornamenti sono quelli normali di ostree.

### 4.1 Pipeline CI (GitHub Actions)

Trigger: ogni giorno, a ogni push e a mano. Matrice: Fedora 44 e 45 (la 45 resta "sperimentale" finché la base stabile non esiste).

1. **detect**: legge dal registry il digest della base e dai repo Fedora le versioni di kernel e libcamera. Se niente è cambiato e le patch sono le stesse, salta.
2. **kmods**: scarica da Koji i `kernel-devel` **esatti** del kernel presente nella base (non quelli correnti del repo: potrebbero essere già più avanti) e il SRPM del kernel,
   da cui estrae i soli sorgenti dei driver da patchare. Così il sorgente è quello del kernel che gira, non un tag upstream. Controllo di sicurezza: se una patch Fedora tocca
   uno di quei file, il job fallisce e lo dice. Compila, firma con la chiave del progetto, produce un RPM `kmod-surface-forge`.
3. **libcamera**: scarica il SRPM di Fedora, applica la serie di patch, ricostruisce con `mock`. Cache per (versione + hash delle patch).
4. **image**: `Containerfile` = base + RPM + file di configurazione, unità systemd, regole udev, binari Rust, KCM. Test di fumo nel container.
5. **sign + publish**: firma cosign, push su `ghcr.io/ccccri/surface-forge:<44|45>` e tag datato.
6. **series-check** (job separato, indipendente): applica le serie di patch su Fedora 44, 45, `updates-testing` e Rawhide. È l'allarme anticipato: dice in anticipo che cosa si romperà.
7. Se un job fallisce: apre una Issue con kernel, versioni, commit e coda del log, e ti avvisa GitHub. La correzione la facciamo insieme in una sessione di Claude Code. L'immagine precedente resta quella che il tablet scarica.

Chiave di firma dei moduli: segreto del repo. Il certificato pubblico sta in `/usr/share/surface-forge/mok.der`. Va registrato nel firmware una volta (MOK).

### 4.2 Aggiornamenti sul tablet

Gli aggiornamenti automatici standard di Kinoite scaricano l'immagine nuova e la attivano al riavvio successivo.
**Guardia di promozione [DECISO]**: `forged` controlla all'avvio che i fix critici funzionino sul nuovo deployment. Se non funzionano
entro un numero di avvii prefissato, notifica e offre il rollback (`rpm-ostree rollback`), senza farlo da solo.

## 5. Installazione **[DECISO]**

**Fase 0: bootstrap** (sulla Kinoite stock, senza dipendenze grafiche che potrebbero mancare). Uno script shell breve e leggibile, scaricato da una release con checksum:
1. controlli (modello da DMI, Kinoite, rete, spazio);
2. scrive in `/etc/containers` la policy e la chiave per verificare l'immagine firmata;
3. mette in coda la registrazione MOK con una password casuale che mostra a schermo;
4. `rpm-ostree rebase ostree-image-signed:docker://ghcr.io/ccccri/surface-forge:44`;
5. riavvio. Passi che richiedono root passano da `pkexec` (la finestra della password di Plasma), non da `sudo` nel terminale.

Un solo riavvio: la schermata blu della MOK compare prima del boot nella nuova immagine. Il bootstrap non esiste come Flatpak: una app in sandbox non può cambiare il sistema operativo.

**Fase 1: assistente al primo avvio** (dentro l'immagine, con Qt/KDE già disponibili): verifica dei fix, calibrazione guidata delle camere (§8), riepilogo.
Quest'ultima richiede un lavoro dell'utente (schermo bianco, copertura dell'obiettivo), quindi non è automatizzabile del tutto.

## 6. Runtime

Componenti, ognuno con un compito solo:

| Componente | Cosa fa | Linguaggio |
|---|---|---|
| `forged` | servizio di sistema: legge il manifest dei fix, esegue i controlli, orchestra le riparazioni, espone lo stato su D-Bus; azioni privilegiate protette da polkit | Rust |
| `surface-nfcd` | lettore NFC sempre attivo, parla con il kernel via netlink (nessun neard) | Rust |
| `forge-notify` | agente di sessione: notifiche con pulsanti, apre la pagina giusta di Impostazioni | Rust o C++ |
| KCM `Surface Forge` | pagina in Impostazioni di Sistema: stato, riparazioni, calibrazione | C++ + QML |
| `forgectl` | CLI per stato, verifica, riparazione, raccolta dei log | Rust |
| strumenti offline | calibrazione e analisi delle immagini, script di CI | Python |

Rust per i demoni: binari piccoli, poca memoria, niente interprete da tenere sveglio su un Pentium, buon supporto per D-Bus (`zbus`) e netlink.
Il KCM deve essere C++: **un KCM in QML puro non può chiamare D-Bus** (**[DA VERIFICARE, S6]**: forse basta un piccolo plugin).

### 6.1 Manifest dei fix

Ogni fix è una cartella `fixes/<id>/` con un `fix.toml`:
```toml
id = "camera-rear"
title = "Fotocamera posteriore"
class = "kernel"            # kernel | userspace | calibration | config
requires = ["mok", "module:ov8865"]
match.dmi = { product_name = "Surface Go" }
check = ["module-loaded ov8865 updates", "node pipewire LNK0"]
repair = ["recalibrate", "restart wireplumber"]
```
Stati: `ok`, `degraded` (riparabile da solo), `needs-reboot`, `needs-user` (MOK, calibrazione), `unsupported`.
I controlli sono dati, non codice: si possono testare senza il tablet.

### 6.2 Monitor

Eventi che lo avviano: avvio, cambio di deployment (`rpm-ostreed`), timer giornaliero, richiesta manuale. Silenzio quando tutto è `ok`.
Una notifica solo per ciò che richiede l'utente (riavvio, MOK, calibrazione, rollback). Riparazione in background per ciò che è `degraded`.
**Non esiste più la ricompilazione sul tablet**: le uniche riparazioni sono ripristinare configurazione, rifare la calibrazione e tornare al deployment precedente.

## 7. Esperienza utente

Il portale principale è **Impostazioni di Sistema**: una voce "Surface" con pagine Stato, Fotocamere, NFC, Audio, Aggiornamenti.
Le notifiche di Plasma servono solo a portarti lì: il pulsante di una notifica apre direttamente la pagina giusta (`kcmshell6`).
Gli extra del vecchio pannello (equalizzatore con import AutoEQ, vista 3D, test della penna e della tastiera) restano **fuori dal nucleo**: arrivano dopo, come funzioni opzionali.

## 8. Calibrazione propria delle camere **[DA VERIFICARE, S4]**

Obiettivo: ottenere lens shading e black level senza usare dati Microsoft, e meglio: per l'esemplare del tablet.
- **Black level**: fotogrammi RAW con l'obiettivo coperto, a gain diversi, per canale.
- **Lens shading**: fotogrammi RAW di un campo bianco uniforme (schermo del desktop a schermo intero con l'obiettivo vicino, come già fatto), stima di una griglia per canale con correzione del contributo dell'illuminante.
- Risultato in `/var/lib/surface-forge/calibration/<sensore>.json`. Un'unità di sistema lo trasforma nel file di tuning di libcamera in `/etc/libcamera/ipa/ipu3/`.
- L'immagine porta un tuning generico di partenza, derivato dalle **mie** misure (dato proprio, quindi includibile).
- Le tabelle Microsoft si possono confrontare **in privato** per controllare che le nostre siano plausibili, ma non entrano mai nella repo.

CCM e white balance vincolato all'illuminante restano fuori dal primo giro (nella vecchia repo la matrice peggiorava gli errori del bilanciamento).
Alternativa studiata e scartata per ora: SoftISP di libcamera. Ha CCM e lens shading ma lavora in software: su un Pentium 4415Y toglierebbe il vantaggio dell'ImgU.

## 9. Test

- **Unit**: logica del manifest, macchina a stati, parser NFC, matematica della calibrazione.
- **CI**: serie di patch su più versioni, build, test di fumo dell'immagine in container.
- **Hardware**: `forgectl verify` sul tablet; gli esperimenti puntuali sono gli spike.
- **Ciclo di sviluppo veloce**: per provare un binario o un file senza aspettare la CI si usa `rpm-ostree usroverlay` (scrivibile fino al riavvio). La CI conferma dopo.

## 10. Fuori scopo

Camera IR (non esposta da libcamera), altri modelli di Surface, filtri GPU e camera virtuale, SoftISP, chiavi di firma condivise tra più utenti.

## 11. Rischi aperti

- Le patch libcamera dipendono dalla versione: la CI avvisa, ma il riadattamento è lavoro.
- Chi controlla la CI controlla il codice che il kernel accetta: la chiave di firma è nei segreti del repo. Accettabile per un uso personale.
- La MOK va confermata a mano una volta, nella schermata blu (e di nuovo dopo una cancellazione delle chiavi del firmware).
- Se la CI si ferma per giorni, il tablet resta sull'ultima immagine che funziona ma non riceve aggiornamenti di sicurezza.
- Il KCM richiede C++: aggiunge competenze e tempo (S6).

## 12. Piano

| Tappa | Contenuto | Fatto quando |
|---|---|---|
| M0 | Repo, documenti, spike S1-S6 sul tablet | ogni spike ha una risposta scritta |
| M1 | CI: moduli kernel firmati + immagine minima che si avvia sul Surface | cameras e NFC funzionano da immagine |
| M2 | libcamera da SRPM con patch livello 1; prova su Fedora 45 | nessun crash, AF stabile, misure ripetibili |
| M3 | Bootstrap + MOK + rebase con un solo riavvio, da installazione pulita | prova da zero sul tablet |
| M4 | `forged` + manifest + monitor + notifiche + `forgectl` | un guasto provocato viene rilevato e riparato |
| M5 | Calibrazione propria + KCM + assistente | colori e vignettatura pari o migliori della vecchia repo |
| M6 | Audio, penna, tastiera, volume spostati nell'immagine | tutti i controlli verdi |
| M7 | Extra opzionali (livello 3, equalizzatore, test) | a scelta |

## 13. Riuso dalla vecchia repo (`surface-go-kinoite`, conservata a parte)

Come **specifica e riferimento**, non come codice da copiare: patch dei driver e di libcamera (rimisurate una a una), documento delle cause radice, strumenti
di misura (`tools/focus-test/`), logica del daemon NFC (riscritta), lista dei problemi noti (`Gotchas`, `Tried and rejected`). Quel che non passa:
`~/mok` e password fissa, tabelle derivate da Microsoft, regole `modprobe install`, `/usr/local/libcamera-patched`, wizard basato su output di script.
