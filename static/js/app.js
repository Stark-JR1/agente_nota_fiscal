const buttons = document.querySelectorAll("[data-run]");
const panel = document.getElementById("runPanel");
const output = document.getElementById("runOutput");
const state = document.getElementById("runState");
const title = document.getElementById("runTitle");

buttons.forEach((button) => {
    button.addEventListener("click", async () => {
        const dryRun = button.dataset.run === "1";
        panel.hidden = false;
        title.textContent = dryRun ? "Executando dry run..." : "Executando conferencia...";
        state.textContent = "processando";
        output.textContent = "Iniciando robo. Aguarde o retorno do processo completo...\n";
        buttons.forEach((item) => item.disabled = true);

        try {
            const response = await fetch("/api/run", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({dry_run: dryRun})
            });
            const data = await response.json();
            output.textContent = `${data.stdout || ""}\n${data.stderr || ""}`.trim();
            state.textContent = data.ok ? "concluido" : `erro ${data.returncode}`;
            if (data.ok) {
                setTimeout(() => window.location.href = data.redirect, 1200);
            }
        } catch (error) {
            state.textContent = "erro";
            output.textContent += `\nErro ao acionar o robo: ${error}`;
        } finally {
            buttons.forEach((item) => item.disabled = false);
        }
    });
});

document.querySelectorAll("[data-pdf]").forEach((button) => {
    button.addEventListener("click", () => {
        const url = button.dataset.pdf;
        const frame = document.getElementById("pdfFrame");
        if (!url || !frame) return;
        const grupo = button.dataset.pdfGroup;
        if (grupo !== undefined) {
            document.querySelectorAll("[data-pdf-group]").forEach((item) => item.classList.remove("active"));
            document.querySelectorAll("[data-pdf-files]").forEach((item) => item.hidden = item.dataset.pdfFiles !== grupo);
        } else {
            const container = button.closest("[data-pdf-files]");
            if (container) container.querySelectorAll("[data-pdf]").forEach((item) => item.classList.remove("active"));
        }
        button.classList.add("active");
        frame.src = url;
    });
});

document.querySelectorAll("[data-approve-process]").forEach((button) => {
    button.addEventListener("click", async () => {
        const processoId = button.dataset.approveProcess;
        if (!window.confirm("Aprovar manualmente este processo? As pendencias serao ignoradas e o PDF final sera criado.")) {
            return;
        }

        const textoOriginal = button.textContent;
        button.disabled = true;
        button.textContent = "Finalizando...";
        try {
            const response = await fetch(`/api/processo/${processoId}/aprovar`, {method: "POST"});
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.erro || "Nao foi possivel finalizar o processo.");
            }
            window.location.href = data.redirect;
        } catch (error) {
            window.alert(`Erro ao aprovar processo: ${error.message}`);
            button.disabled = false;
            button.textContent = textoOriginal;
        }
    });
});
