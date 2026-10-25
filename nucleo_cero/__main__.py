"""CLI: python -m nucleo_cero {pesos|mejorar|benchmark} ..."""
import argparse
import glob
import json
import logging

CONFIG = dict(usar_esrgan=False, fondo_clasico=True, restaurador='gfpgan', mezcla=0.5,
              cara_minima=64, umbral_identidad=0.80, proteger_caras=True)  # = CONFIG_SUELTA del notebook


def main():
    ap = argparse.ArgumentParser(prog='nucleo_cero')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('pesos', help='descarga los modelos (~450 MB)')
    m = sub.add_parser('mejorar', help='mejora una o varias fotos')
    m.add_argument('fotos', nargs='+')
    m.add_argument('-o', '--salida', default='data/output')
    m.add_argument('--esrgan', action='store_true', help='fondo con Real-ESRGAN (puede posterizar fotos de WhatsApp)')
    b = sub.add_parser('benchmark', help='mide tiempo por foto')
    b.add_argument('carpeta', help='carpeta con fotos (jpg/png)')
    b.add_argument('-n', type=int, default=20)
    b.add_argument('--esrgan', action='store_true')
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    if a.cmd == 'pesos':
        from .modelos import descargar_pesos
        return descargar_pesos()

    from . import motor
    cfg = dict(CONFIG, usar_esrgan=a.esrgan)
    if a.cmd == 'mejorar':
        for f in a.fotos:
            motor.mejorar_foto(f, carpeta_salida=a.salida, **cfg)
    else:
        fotos = sorted(glob.glob(f'{a.carpeta}/*.jp*g') + glob.glob(f'{a.carpeta}/*.png'))[:a.n]
        from .benchmark import ejecutar_benchmark
        res = ejecutar_benchmark(lambda f: motor.mejorar_foto(f, guardar=False, verbose=False, **cfg), fotos)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        print(f'dispositivo: {motor.DEVICE}')


if __name__ == '__main__':
    main()
