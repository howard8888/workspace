# -*- coding: utf-8 -*-
"""
CCA8 Temporal Module
cca8_temporal.py


-Time helpers for stamping bindings (e.g., `meta["created_at"]`) and optional period/year tagging. The WorldGraph itself is atemporal
except for anchors like `NOW`. Temporal semantics are layered via meta and planning constraints (i.e., we do not bake clock logic
into the graph -- we should keep it in this module or the runner module).
-WorldGraph stays an episode index with anchors like "NOW" while time semantics are layered via 'meta' and planning constraints.
-ISO-8601 strings -- format is YYYY-MM-DDThh:mm:ss where 'T' is a separator between date and time, i.e., timespec = 'seconds', with
optional period/year and planning constraints.
-Naive local time, no timezone
-Provenance stamps everywhere any actions write -- each time a binding is created there is a stamp 'created_at' (ISO-8601, seconds precision)
by the policy creating it and meta["policy"]= "policy:<name>" .
-Note that at present, this Temporal Module does not participate in timestamping, i.e., meta["policy"]= "policy:<name>" . The policies are
  timestamped directly in the Controller Module (e.g., FollowMom, Rest, etc)

-Thus, much of this module is to support the TemporalContext vector. Why a temporal vector if we already have timestamps?
-Our timestamps, i.e., essentially ISO-8601 wall-clock time, is great for provenance and logs, but it is less useful for:
1. Segmentation -- e.g., "When did one episode end and the next begin?"
-we could invent ad-hoc boundaries, e.g., if there is a 5 second gap then that is a boundary, etc, but these rules will fail, e.g., sim speed varies
2. Similarity Search -- "Fetch things that happened around the same time as X."  With just a timestamp you're doing range filters and unit conversions--
nothing really says "nearby" in a smooth way.
-the vector is not as much work computationally as it sounds -- we use a unit-norm vector that either drifts with time (small steps) but jumps
(at event boundaries), giving us essentially a cheap, geometry-based notion of "near in time" with no parsing, no units -- just dot products.
-cos(v_now, v_then) ~ 1.0 implies close in time.
-cos() falling below a threshold -- likely a boundary.
-We pick a threshold τ (e.g., 0.9) for boundary detection by comparing the current vector to the last boundary vector.

-After each drift step or jump boundary we L2 re-normalize the vector, i.e., back to length 1, since we are assuming cosine = dot product
- cosine(θ) = cos(θ) = "cos" shorthand -- for non-zero vectors it gives a measure of similarity of vectors across any number of dimensions
- cos(θ) = (u <dot> v)/ (||u||*||v||)), thus θ = arccos( (u <dot> v)/ (||u||*||v||)))
- since unit-norm ||u|| = ||v|| = 1, therefore cos(θ) = u <dot> v  and thus (θ) = arccos(u <dot> v)
  thus, for unit-norm vectors, cosine equals the dot product.
- same direction with θ= 0 then cos = 1
- orthogonal with θ = 90 then cos = 0
- opposite direction with θ = 180 then cos = -1
- e.g., u = [1,2,2], v= [2,1,2], thus dot = 8;  ||u|| = sqrt(9) = 3, ||v|| = sqrt(9) = 3; cos = 8/(3*3) = 0.889; θ = arccos(.889) = 27 deg
- e.g., u = [1,0,0], v = [0,1,0], thus dot = 0, thus cos = 0, thus θ = 90 deg (orthogonal)
- this math is relatively simple, thus I have decided not use Numpy for now -- the Python code is fast enough
- the renormalization (see code) is also simple, i.e., L2 norm and divide, so again Python code is fast enough for now

-The vector itself is a 128-dim (adjustable dims) list of floats, always re-normalized to a unit length vector
-there is a demo block of code
e.g., TemporalContext vector at 8-D is:   TemporalContext(dim=8, sigma=0.02, jump=0.25, _v=[-0.08324498290455759, -0.09989120918728571, -0.064310263015913,
 0.4055554829134334, -0.07371129300238069, -0.8650626294215049, 0.19198953150999917, -0.15444828179956657])
 ||v0||≈1: 1.0
cos(v0, v1) after step():    0.9993346922371369
cos(v0, v2) after boundary(): 0.9303704646916311
-See the vector algebra utilities and demos below for a review of the math, particularly cosine similarity.
-note that for unit vectors 'def cos(a, b): return sum(x*y for x, y in zip(a, b))' should give similar results as our helper dot(a, b) .

-What do the contents of the TemporalContext vector really mean?
-Note from the code that effectively, as shown below, when we initialize in __post_init__  we are sampling each
 coordinate from a standard normal and then normalizing -- that is why components don't have human meaning.
-Then each tick we can add small Gaussian noise to every coordinate and re-normalize to make a tiny change in direction == a drift step.
  For larger boundary jumps we add a bigger noise which produces a larger change in direction which we exploit for episode segmentation.
-A unit vector in R^n-dim acts as a time fingerprint for "NOW".
-We update it with tiny drift steps and bigger boundary jumps.
-We don't read it component-by-component but instead we compare whole vectors to tell us near-in-time versus far-in-time.
-Consider a simple 4-D TemporalContext vector: e.g.,  v = [-0.19545054, -0.26136825, -0.14239240,  0.93445713]
-  if we square the components [[0.03820, 0.06831, 0.02028, 0.87321] and sum them [~= 1.0] then the square root is ~= 1.0
- given that 4th axis squared is .873 it indicates that about 87.3% of the direction is along the 4th axis with smaller contributions on the other axes
- it does not actually mean that the 4th time unit is dominant, just that the direction is mostly aligned with axis #4
-The axes themselves are arbitrary.
-Each float is just a coordinate projection of the current time-state onto one basis axis.
-The sign indicates which side of the axis while the magnitude indicates how much of the direction along that axis
-Meaning from the context vector only emerges by comparison. If there is a high dot product, then that means it is nearby in time. If there is a low
  dot product, then likely there was an event boundary.
-Effectively, by comparing vectors we have a cheap segmentation and retrieval mechanism, without having to invent manually-tuned clock rules

-Note that our context vector is not a learned embedding, but is a procedural “soft clock” we control.
-A learned embedding is a vector produced by a trained model -- its geometry emerges from training.
-However, our vector is produced by a fixed algorithm, no training, i.e., a procedural soft clock effectively.
-As noted above, when we initialize a context vector in __post_init__ , each tick we add tiny Gaussian noise==drift and renormalize.
-We can adjust how fast time moves via sigma==drift and how hard a chapter break feels via jump==boundary strength.
-It will be reproducible in theory if we set the same seed.
-It is content-agnostic -- it doesn't encode what happened, only when/near what it happened in the run's flow
-It is 'cheap' in that it uses O(d) math, pure Python, no training, no GPU.
-It provides us with segmentation -- use a dot-product threshold against the last boundary vector to cut episodes.
-It provides us with temporal similarity -- can fetch things from around the same time.
-In the future we can combine it with learned content embeddings as second orthogonal axis.
-However, keep in mind that won't 'learn' dataset-specific time patterns but instead it encodes relative time

-Given the above background, we can concisely consider how we utilize the temporal vectors.
-Again, they allow allow segmentation of new episodes and they allow similarity searches.
-They have relative values and not meant to be globally comparable across different runs.
-It's not a learned embedding but rather a procedural 'soft clock' we control.
-They are not a replacement for real timestamps -- as noted above we still stamp ISO-8601 for audit/provenance.
-After each drift/jump we L2-normalize the vector to length 1.
-step() adds tiny Gaussian noise -- very small direction change
-boundary() adds bigger noise -- noticeable change
-The result is to get a smooth trajectory with occasional boundary breaks


Nov 1, 2025
i) What timestamps/provenance we stamp now--
Bindings created by policies get:
meta["created_at"]: ISO-8601 (seconds precision).
meta["ticks"]: the runner’s tick counter.
meta["tvec64"]: 64-bit sign-bit hash of the temporal vector at creation (if ctx.temporal exists).
Edges created via attach='now'|'latest' inherit the same meta, because WorldGraph.add_predicate(...) forwards meta into its auto edge. (Explicit add_edge(...) calls don’t currently pass meta unless you add it.)
Autosave files get a file-level saved_at timestamp in the runner.

ii) How we use TemporalContext now--
Runner creates a temporal vector and drifts it once per instinct/autonomic tick.
On a successful write (graph grew), runner takes a boundary jump and updates tvec_last_boundary.
Runner performs a thresholded segmentation check (τ=0.90) each tick and triggers a boundary when the cosine to the last boundary falls below τ.
Policies don’t import Temporal directly; they just read a compact tvec64() from ctx via _policy_meta(...), so every write gets a time-fingerprint alongside created_at.
Snapshots show a tiny TEMPORAL readout (params, cos_to_last_boundary, vhash64) so you can track time dynamics without dumping the whole 128-D vector.

"""

# --- Imports -------------------------------------------------------------
# Standard Library Imports
from __future__ import annotations
from dataclasses import dataclass, field
import random
import math
from typing import List

# PyPI and Third-Party Imports
# --none at this time at program startup--

# CCA8 Module Imports
# --none at this time at program startup--


# --- Public API index and version, constants ---------------------------------
__version__ = "0.2.0"
__all__ = ["TemporalContext", "__version__"]


# -----------------------------------------------------------------------------
# TemporalContext
# -----------------------------------------------------------------------------

@dataclass
class TemporalContext:
    """128-D unit-norm TemporalContext vector with drift and boundary jumps.

    -The rationale and use of the Temporal Context vector is described in detail in the module docstring.

    fields (become parameters and once an instance is created become attributes)
    ------
    dim -- number of dimensions to generate TemporalContext vector.
    sigma -- amount of drift with each tick.
    jump -- amount of change with boundary change.
    _v -- original TemporalContext vector we initialize in the __post_init__()

    See module docstring for more details.

    """
    dim: int = 128        # dimension of the TemporalContext vector
    sigma: float = 0.02   # per-tick drift scale
    jump: float = 0.25    # event-boundary jump scale
    _v: List[float] = field(default_factory=list)  #original TemporalContext vector


    def __post_init__(self) -> None:
        """
        Initialize the initial TemporalContext vector _v if it empty.
        Sample each coordinate from a standard normal and normalize.

        """
        if not self._v:
            vals = [random.gauss(0.0, 1.0) for _ in range(self.dim)]
            #e.g., dim=4 -- [-0.14409032957792836, -0.1729036003315193, -0.11131586156766246, 0.7019837250988631]
            self._v = self._normalize(vals)
            #e.g., [-0.19326972277945167, -0.23191723553917554, -0.14930901864932258, 0.9415774142717086]

    def vector(self) -> list[float]:
        """Return a defensive copy of the current context vector.
        -Purpose is to return a safe copy of self._v, thereby protecting the original _v from being modified.
        """
        return list(self._v)

    def step(self) -> list[float]:
        """Drift the temporal vector by Gaussian noise (self.sigma), renormalize to unit length, and return a copy.
        -See the module docstring for explanation of drift noise and jump noise.
        -Add Gaussian noise (σ = self.sigma) to each dimension, then re-normalize.
        """
        vals = [a + random.gauss(0.0, self.sigma) for a in self._v]
        self._v = self._normalize(vals)
        return self.vector()

    def boundary(self) -> list[float]:
        """Apply a larger event-boundary jump (self.jump), renormalize to unit length, and return a copy.
        -See the module docstring for explanation of drift noise and jump changes
        -The jump noise which is influenced by the jump parameter is applied in a gaussian fashion to each dimension.
        """
        vals = [a + random.gauss(0.0, self.jump) for a in self._v]
        self._v = self._normalize(vals)
        return self.vector()

    @staticmethod
    def _normalize(vals: list[float]) -> list[float]:
        """Return a unit-norm copy of `vals` (L2 normalize); safeguards against zero norm by using 1.0.
        e.g., in 4-dim example shown in __post_init__() --
            input vector to normalize:  [-0.14409032957792836, -0.1729036003315193, -0.11131586156766246, 0.7019837250988631]
            returned normalized vector: [-0.19326972277945167, -0.23191723553917554, -0.14930901864932258, 0.9415774142717086]
            verified magnitude is 1.0
        note - this is a staticmethod and can be used by other parts of the code directly without an instance
          e.g., normalize_vector = TemporalContext._normalize(...)
          or within TemporalContext class, as in the example above, we can call it via self, e.g., self._v = self._normalize(vals)

        """
        s = math.sqrt(sum(a * a for a in vals)) or 1.0
        return [a / s for a in vals]

# -----------------------------------------------------------------------------
# Vector Algebra Utilities and Demos
# -----------------------------------------------------------------------------

def dot(a: list[float], b: list[float]) -> float:
    """Dot product (also cosine if a and b are unit vectors).
    -Note that def cos(a, b): return sum(x*y for x, y in zip(a, b)) should give same result.
    """
    return math.fsum(x*y for x, y in zip(a, b))

def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity, robust even if inputs aren’t perfectly unit-length.
    """
    na = math.sqrt(math.fsum(x*x for x in a))
    nb = math.sqrt(math.fsum(y*y for y in b))
    return (dot(a, b) / (na * nb)) if (na and nb) else 0.0

def demo_temporalcontext(n:int =18) -> bool:
    '''demonstration of n-dim TemporalContext vector.

    parameters:
        n == dim -- number of dimensions to generate TemporalContext vector.

    intrinsic parameters:
        sigma -- amount of drift with each tick.
        jump -- amount of change with boundary change.

    returns:
        True -- able to generate and analyze an n-dim TemporalContext vector.
        False -- some aspect of the code failed, for future development in particular if more advanced processing.

    sample output:
        -parameters of TemporalContext 't' dim, sigma, jump:  8 0.02 0.25
        -TemporalContext t is:  TemporalContext(dim=8, sigma=0.02, jump=0.25, _v=[-0.08324498290455759, -0.09989120918728571, -0.064310263015913, 0.4055554829134334,
        -0.07371129300238069, -0.8650626294215049, 0.19198953150999917, -0.15444828179956657])
        ||v0||≈1: 1.0
        --->cos(v0, v0) should be identical:  1.0000000000000002
        -vector v0 initial unit vector is:  [-0.08324498290455759, -0.09989120918728571, -0.064310263015913, 0.4055554829134334, -0.07371129300238069,
        -0.8650626294215049, 0.19198953150999917, -0.15444828179956657]
        -vector v1 small drift is:  [-0.08694440371372042, -0.09686079396078362, -0.05922849415148321, 0.42569431974094746, -0.060136070625905036,
        -0.8565498350398787, 0.1759285846605129, -0.17346514081847536]
        --->cos(v0, v1) after step():    0.9993346922371369
        -vector v2 larger jump is:  [-0.019328381304339386, 0.1759978987148655, -0.037205977359353166, 0.3042021363842727, 0.05549384981551121, -0.9298287064384144,
        0.0745877922595042, -0.0387762730759063]
        --->cos(v0, v2) after boundary(): 0.9303704646916311

    '''
    try:
        if n <= 0:
            print('n must be a positive integer -- set to n=8')
            n=8
        print(f'\n Demo of {n}-D TemporalContext Vector\n')
        def cos(a, b): return sum(x*y for x, y in zip(a, b))
        #should give same result as dot product since this is actually a dot product, albeit for unit-norm vectors
        random.seed(42) #note -- this will set random for module-global -- protect in future if an issue
        sigma = 0.02
        jump = 0.25
        print("-parameters of TemporalContext 't' dim, sigma, jump: ", n, sigma, jump)
        t = TemporalContext(n, sigma, jump)
        print('-TemporalContext t is: ', t)
        v0 = t.vector()        # initial unit vector
        print("||v0||≈1:", sum(x*x for x in v0) ** 0.5)
        print("--->cos(v0, v0) should be identical: ", cos(v0, v0))
        print("--->dot(v0, v0) should be identical: ", dot(v0, v0))
        print('-vector v0 initial unit vector is: ', v0)
        v1 = t.step()          # small drift
        print('-vector v1 small drift is: ', v1)
        print("--->cos(v0, v1) after step():   ", cos(v0, v1))  # ~0.999… (very similar)
        print("--->dot(v0, v1) after step():   ", dot(v0, v1))  # ~0.999… (very similar)
        v2 = t.boundary()      # larger jump
        print('-vector v2 larger jump is: ', v2)
        print("--->cos(v0, v2) after boundary():", cos(v0, v2))  # noticeably smaller
        print("--->dot(v0, v2) after boundary():", dot(v0, v2))  # noticeably smaller
        print("--->true cosine(v0, v2) after boundary: ", cosine(v0, v2))
        return True
    except Exception as e:
        print(f'**failure -- {e} -- occurred running demo_temporalcontext()**')
        return False

if __name__ == "__main__":
    #run demo_temporalcontext directly to see demo output, i.e.,   >python cca8_temporal.py
    demo_temporalcontext(4)
