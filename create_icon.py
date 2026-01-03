from PIL import Image, ImageDraw
import os


def create_pwa_icon(input_path, output_path, size=512):
    """
    Crea un'icona PWA perfetta con sfondo trasparente

    Args:
        input_path: percorso dell'immagine originale
        output_path: percorso dove salvare l'icona
        size: dimensione dell'icona (default 512x512)
    """

    # Apri l'immagine originale
    img = Image.open(input_path)

    # Converti in RGBA per supportare la trasparenza
    img = img.convert('RGBA')

    # Crea una nuova immagine quadrata con sfondo trasparente
    new_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))

    # Ridimensiona l'immagine originale mantenendo le proporzioni
    # Usa l'80% dello spazio per lasciare un po' di padding
    target_size = int(size * 0.90)
    img.thumbnail((target_size, target_size), Image.Resampling.LANCZOS)

    # Calcola la posizione per centrare l'immagine
    x = (size - img.width) // 2
    y = (size - img.height) // 2

    # Incolla l'immagine al centro
    new_img.paste(img, (x, y), img)

    # Salva l'immagine
    new_img.save(output_path, 'PNG')
    print(f"✓ Icona creata: {output_path}")


def create_circular_icon(input_path, output_path, size=512):
    """
    Crea un'icona circolare perfetta che finisce esattamente al bordino argentato
    """

    # Apri l'immagine originale
    img = Image.open(input_path)
    img = img.convert('RGBA')

    # Ridimensiona l'immagine originale al 100% della dimensione target
    # così il cerchio occupa tutto lo spazio disponibile
    img = img.resize((size, size), Image.Resampling.LANCZOS)

    # Crea una maschera circolare delle stesse dimensioni
    mask = Image.new('L', (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)

    # Crea l'output con sfondo trasparente
    output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    output.paste(img, (0, 0))
    output.putalpha(mask)

    # Salva
    output.save(output_path, 'PNG')
    print(f"✓ Icona circolare creata: {output_path}")


# Esempio di utilizzo:
if __name__ == "__main__":
    # Percorsi dei file
    input_file = "beesy_original.png"  # La tua immagine originale
    output_512 = "beesy_icon_512.png"
    output_192 = "beesy_icon_192.png"
    output_circular = "beesy_icon_circular_512.png"

    # Verifica che il file esista
    if not os.path.exists(input_file):
        print(f"⚠ File non trovato: {input_file}")
        print("\nCome usare questo script:")
        print("1. Salva la tua immagine come 'beesy_original.png'")
        print("2. Esegui: python create_icon.py")
        print("\nOppure modifica il nome del file nello script")
    else:
        # Crea le icone
        print("Creazione icone in corso...")

        # Icona standard con sfondo trasparente
        create_pwa_icon(input_file, output_512, 512)
        create_pwa_icon(input_file, output_192, 192)

        # Icona circolare (come Chrome)
        create_circular_icon(input_file, output_circular, 512)

        print("\n✓ Fatto! Usa 'beesy_icon_512.png' nel tuo manifest")
