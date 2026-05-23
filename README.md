# Sudoku — App Android

Application Sudoku complète développée en Python avec **Kivy**, empaquetable en **APK Android** via **Buildozer**.

## Contenu du dossier

```
sudoku_app/
├── main.py            ← Code principal de l'app
├── buildozer.spec     ← Configuration Android
├── icon.png           ← Logo (512x512)
├── presplash.png      ← Écran de démarrage (1024x1024)
├── make_logo.py       ← Script qui génère icon.png et presplash.png
└── README.md          ← Ce fichier
```

## Tester sur ordinateur avant de générer l'APK

C'est plus rapide pour vérifier que tout marche.

```bash
# Installer Kivy
pip install kivy[base]==2.3.0 pillow

# Lancer l'app (s'affiche dans une fenêtre 420x820)
cd sudoku_app
python main.py
```

Sur ordinateur tu peux jouer au clavier : flèches pour bouger, 1-9 pour saisir, Suppr/Retour pour effacer, Ctrl+Z, N (notes), Espace ou P (pause), Échap (sortir mode rapide).

## Générer l'APK Android

⚠️ **Le build APK ne fonctionne QUE sous Linux (ou WSL2 sur Windows, ou macOS).**
Pas possible directement sous Windows natif à cause des outils Android.

### Option A — Sur Linux / WSL2 (recommandé)

#### 1. Installer les dépendances système

```bash
sudo apt update
sudo apt install -y python3-pip git zip unzip openjdk-17-jdk \
    autoconf automake libtool libltdl-dev pkg-config zlib1g-dev \
    libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev \
    libssl-dev build-essential ccache
```

#### 2. Installer Buildozer + Cython

```bash
pip install --user buildozer cython==0.29.36 virtualenv
```

Ajoute `~/.local/bin` dans ton PATH si ce n'est pas fait :
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### 3. Lancer le build

```bash
cd sudoku_app
buildozer android debug
```

Le PREMIER build télécharge le SDK et NDK Android (~3 Go). Compter **30 à 60 minutes**. Les builds suivants prennent 1 à 5 minutes.

L'APK généré sera dans `sudoku_app/bin/`, fichier nommé du type :
```
sudoku-1.0-arm64-v8a_armeabi-v7a-debug.apk
```

#### 4. Installer sur le téléphone

Trois façons :

**Par câble USB** (le plus simple avec le mode debug Android activé) :
```bash
buildozer android deploy run
```

**Par copie manuelle** : transfère l'APK sur le téléphone (Bluetooth, email, Drive), ouvre-le dans le gestionnaire de fichiers. Android demandera d'autoriser l'installation depuis cette source.

**Pour partager** : envoie le `.apk` à qui tu veux, ils auront besoin d'autoriser l'installation depuis source inconnue.

### Option B — Sans Linux : utiliser une VM ou GitHub Actions

Si tu es sous Windows sans WSL, deux solutions :

1. **WSL2** : installe Ubuntu via le Microsoft Store, puis suis l'option A à l'intérieur.

2. **GitHub Actions** (gratuit, build en ligne, **recommandé si tu es sous Windows**) :

   Un workflow est déjà inclus dans le projet : `.github/workflows/build-apk.yml`

   Étapes :
   - Crée un repo GitHub (public ou privé) et pousse tous les fichiers de `sudoku_app/`
   - Va dans l'onglet **Actions** du repo
   - Le workflow "Build Android APK" se lance automatiquement à chaque push
   - Une fois terminé (~30 min la première fois, ~10 min ensuite), clique sur le run → en bas dans **Artifacts**, télécharge `sudoku-apk.zip` qui contient l'APK
   - Tu peux aussi lancer manuellement le build via le bouton **Run workflow**

   Avantage : aucun outil à installer sur ta machine.

## Distribuer l'app

### Pour ton usage personnel
L'APK debug suffit. Active "Sources inconnues" dans les paramètres Android > Sécurité, puis installe.

### Sur le Google Play Store
Il faut :
1. Build en mode release : `buildozer android release`
2. Signer l'APK avec une clé (Buildozer guide l'opération)
3. Compte développeur Google Play (25 $ une fois)
4. Soumettre via la Play Console

## Personnalisation

- **Couleurs** : modifier la classe `T` au début de `main.py`
- **Icône** : remplacer `icon.png` (512×512, format PNG)
- **Écran de démarrage** : remplacer `presplash.png`
- **Nom de l'app** : champ `title` dans `buildozer.spec`
- **Identifiant** : `package.name` et `package.domain` dans `buildozer.spec`

Pour régénérer le logo avec un style différent, édite `make_logo.py` et relance :
```bash
python make_logo.py
```

## Sauvegarde des stats

Sur Android, les statistiques et la partie en cours sont stockées dans le dossier privé de l'app (`/data/data/org.sudoku.app/files/`). Elles sont conservées tant que l'app n'est pas désinstallée.

## Dépannage

**"buildozer: command not found"** → vérifie `~/.local/bin` dans le PATH.

**Build échoue avec "JAVA_HOME"** → installe `openjdk-17-jdk` et essaye :
```bash
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
```

**Erreur de dépendance Cython** → installe la version 0.29.36 (les plus récentes cassent parfois) :
```bash
pip install cython==0.29.36
```

**Build long** → c'est normal au premier lancement (téléchargement Android SDK/NDK). Les builds suivants sont rapides.

**App qui crashe au lancement sur le téléphone** → connecte le téléphone et regarde les logs :
```bash
buildozer android logcat | grep python
```

## Licence

Code personnel — fais-en ce que tu veux.
