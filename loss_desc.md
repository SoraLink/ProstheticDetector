# 3. Proposed Objective Function: Pro-Loss

To address the geometric ambiguity (e.g., "stick" limbs) and semantic inconsistencies (e.g., "flesh-growing-from-metal") in prosthetic pose estimation, we propose a composite objective function.

The total loss is defined as a weighted sum:

$$
\mathcal{L}_{total} = \mathcal{L}_{pose} + \lambda_{cls} \mathcal{L}_{cls} + \lambda_{bio} \mathcal{L}_{bio}
$$

Where $\lambda_{cls}$ and $\lambda_{bio}$ are balancing coefficients.

---

### 1. Pose Regression Loss ($\mathcal{L}_{pose}$)

**Purpose:** To localize the spatial coordinates of keypoints.

**Design Intuition:**
Standard pose estimation losses (like MSE on Heatmaps) are **geometrically agnostic**. This is crucial for "stick/pylon" prosthetics where the *Heel* and *Toe* are physically coincident. Unlike bone-length constraints, MSE allows multiple Gaussian peaks to overlap without penalty.

**Formulation:**

$$
\mathcal{L}_{pose} = \frac{1}{K} \sum_{k=1}^{K} V_k \cdot \| H_k - \hat{H}_k \|_2^2
$$

* $H_k$: Predicted heatmap for the $k$-th keypoint.
* $\hat{H}_k$: Ground Truth Gaussian heatmap.
* $V_k \in \{0, 1\}$: Visibility indicator (loss is only computed for visible joints).

---

### 2. Semantic Classification Loss ($\mathcal{L}_{cls}$)

**Purpose:** To explicitly categorize the semantic attribute of each keypoint into **Normal (N)**, **[Welcome file.md](..%2F..%2FDownload%2FWelcome%20file.md)Prosthetic (P)**, or **Missing (M)**.

**Design Intuition:**
This ensures the model learns *what* the keypoint is, not just *where* it is.

**Formulation:**

$$
\mathcal{L}_{cls} = - \frac{1}{K} \sum_{k=1}^{K} \sum_{c \in \{N, P, M\}} V_k \cdot y_{k,c} \log(p_{k,c})
$$

* $y_{k,c}$: One-hot Ground Truth label.
* $p_{k,c}$: Predicted probability for class $c$.

---

### 3. Bio-Contrastive Probability Loss ($\mathcal{L}_{bio}$)

**Purpose:** To enforce **Biological Monotonicity**.
It acts as a hard semantic barrier, ensuring that biological attributes (Normalcy) strictly terminate at the amputation point and do not propagate to the prosthetic chain.

**Design Intuition:**
We use a **Probabilistic Contrastive Loss** mechanism:
1.  **Positive Anchor:** The **Amputation Point (Residual Limb)**. We maximize its probability of being "Normal".
2.  **Negative Samples:** All **Descendant Joints** (Prosthetic/Missing). We minimize their probability of being "Normal".
3.  **Dynamic Masking:** We strictly mask out occluded joints ($V=0$) to prevent noise fitting.
4.  **Temperature Scaling:** We use $\tau$ to sharpen the probability distribution.

**Formulation:**
Let $\mathcal{A}$ be the set of Amputation Points. For a specific point $a \in \mathcal{A}$, let $\mathcal{D}_a$ be the set of its descendants.

$$
\mathcal{L}_{bio} = - \frac{1}{|\mathcal{A}|} \sum_{a \in \mathcal{A}} \mathbb{I}(V_a) \cdot \log \left( \frac{\exp(P^{(N)}_a / \tau)}{\exp(P^{(N)}_a / \tau) + \sum_{j \in \mathcal{D}_a} \mathbb{I}(V_j) \cdot \exp(P^{(N)}_j / \tau)} \right)
$$

**Where:**
* $P^{(N)}_a$: The predicted probability (after Softmax) of the amputation point being **Normal**.
* $P^{(N)}_j$: The predicted probability of the descendant joint being **Normal**.
* $\tau$: Temperature coefficient (e.g., $\tau=0.07$).
* $\mathbb{I}(V)$: Indicator function handling visibility. Occluded joints are excluded.