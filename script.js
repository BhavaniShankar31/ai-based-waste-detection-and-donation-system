const fileInput = document.getElementById("fileInput");
const preview = document.getElementById("preview");
const detectBtn = document.getElementById("detectBtn");
const resultBox = document.getElementById("result");

let imageBase64 = "";

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  const reader = new FileReader();
  reader.onloadend = () => {
    preview.src = reader.result;
    preview.style.display = "block";
    imageBase64 = reader.result.split(",")[1];
  };
  if (file) reader.readAsDataURL(file);
});

detectBtn.addEventListener("click", async () => {
  if (!imageBase64) {
    alert("Please upload an image first!");
    return;
  }

  resultBox.innerHTML = "Analyzing...";
  let lat = null, lon = null;

  if (navigator.geolocation) {
    await new Promise((res) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          lat = pos.coords.latitude;
          lon = pos.coords.longitude;
          res();
        },
        () => res()
      );
    });
  }

  const response = await fetch("/detect", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image: imageBase64, lat, lon }),
  });

  const data = await response.json();
  if (data.error) {
    resultBox.innerHTML = `<p style='color:red'>${data.error}</p>`;
    return;
  }

  let html = `<p><strong>Detected Item:</strong> ${data.item}</p>
              <p><strong>Category:</strong> ${data.category}</p>`;

  if (data.category === "donatable" && data.donation_places.length > 0) {
    html += "<h4>Nearby Donation Centers:</h4><ul>";
    data.donation_places.forEach((p) => {
      html += `<li>${p.name} — ${p.address}</li>`;
    });
    html += "</ul>";
  }

  resultBox.innerHTML = html;
});
