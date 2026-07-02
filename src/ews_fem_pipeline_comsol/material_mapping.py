"""Material conversion helpers for COMSOL builder generation."""


def linearize_mooney_rivlin(material: dict[str, object]) -> tuple[float, float]:
    """Infer a small-strain linear elastic approximation from source material inputs.

    The COMSOL route currently uses this approximation for initial dynamic
    sensitivity runs:
    - shear modulus ``G ~= 2 * (c1 + c2)``
    - bulk modulus ``K`` from the source-case material
    - ``E`` and ``nu`` from the standard isotropic linear elastic relations
    """
    bulk_modulus = float(material.get("bulk_modulus", 1.0))
    coef1 = float(material.get("coef1", 0.0))
    coef2 = float(material.get("coef2", 0.0))
    shear_modulus = max(2.0 * (coef1 + coef2), 1e-9)
    youngs_modulus = 9.0 * bulk_modulus * shear_modulus / (3.0 * bulk_modulus + shear_modulus)
    poissons_ratio = (3.0 * bulk_modulus - 2.0 * shear_modulus) / (2.0 * (3.0 * bulk_modulus + shear_modulus))
    poissons_ratio = min(max(poissons_ratio, -0.49), 0.499)
    return youngs_modulus, poissons_ratio
