from PIL import Image, ImageFilter


def blur_image(source: str, destination: str, radius: int = 10):
    """Blur an image and save it to a new file.

    Args:
        source (str): The path to the source image
        destination (str): The path to save the blurred image
        radius (int): The blur radius
    """
    img = Image.open(source)
    blurred = img.filter(ImageFilter.GaussianBlur(radius))
    blurred.save(destination)
