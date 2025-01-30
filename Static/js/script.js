// Zorg ervoor dat de socket verbinding wordt opgebouwd zodra de pagina wordt geladen
const socket = io.connect("https://lucky13-bot-8b1fa5884ddc.herokuapp.com/"); 

// UI elementen
let saldoElement = document.getElementById("balance");
let activeTradesContainer = document.getElementById("trades-list");
let chartContainer = document.getElementById("chart");
let errorMessageContainer = document.getElementById("errorMessages");
let botStatusIndicator = document.getElementById("bot-status");

// Chart.js instance
let balanceChart = null;

// Update de balans op de pagina
function updateBalance(data) {
    saldoElement.innerText = `Saldo: ${data.balance.toFixed(2)} USDT`;
}

// Update de lijst van actieve trades
function updateActiveTrades(data) {
    activeTradesContainer.innerHTML = ""; // Clear bestaande trades

    data.trades.forEach(trade => {
        const tradeElement = document.createElement("div");
        tradeElement.className = `trade-item ${trade.current_profit > 0 ? 'success' : 'failure'}`;
        tradeElement.innerHTML = `
            <span>Trade: ${trade.symbol}</span>
            <span>Status: ${trade.current_profit > 0 ? 'Profit' : 'Loss'}</span>
            <span>Winst/Verlies: ${trade.current_profit > 0 ? '+' : ''}${(trade.current_profit * 100).toFixed(2)}%</span>
        `;
        activeTradesContainer.appendChild(tradeElement);
    });
}

// Foutmeldingen tonen
function showErrorMessages(messages) {
    errorMessageContainer.innerHTML = ""; // Clear bestaande berichten

    messages.forEach(message => {
        const messageElement = document.createElement("div");
        messageElement.className = "error-message";
        messageElement.innerText = message;
        errorMessageContainer.appendChild(messageElement);
    });
}

// Grafiek bijwerken
function updateChart(data) {
    if (balanceChart) {
        balanceChart.destroy(); // Verwijder de bestaande grafiek om duplicatie te voorkomen
    }

    const ctx = chartContainer.getContext("2d");
    const chartData = {
        labels: data.labels,
        datasets: [{
            label: "Saldo per maand",
            data: data.values,
            borderColor: '#007bff',
            backgroundColor: 'rgba(0, 123, 255, 0.2)',
            fill: true,
            borderWidth: 2
        }]
    };

    balanceChart = new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: {
            responsive: true,
            scales: {
                x: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Bot status bijwerken
function updateBotStatus(isRunning) {
    if (botStatusIndicator) {
        botStatusIndicator.innerText = isRunning ? "✅ Bot is actief" : "❌ Bot is gestopt";
        botStatusIndicator.style.color = isRunning ? "green" : "red";
    }
}

// Socket.io event handlers
socket.on('update_balance', updateBalance);
socket.on('update_trades', updateActiveTrades);
socket.on('update_chart', updateChart);
socket.on('error_messages', showErrorMessages);
socket.on('bot_status', updateBotStatus); // Ontvang bot status updates

// Exporteer de grafiek naar een CSV bestand
function exportChartToCSV() {
    if (!balanceChart) {
        alert("Geen gegevens beschikbaar om te exporteren.");
        return;
    }

    const labels = balanceChart.data.labels;
    const values = balanceChart.data.datasets[0].data;

    let csvContent = "Label,Value\n";
    labels.forEach((label, index) => {
        csvContent += `${label},${values[index]}\n`;
    });

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `chart_${new Date().toLocaleDateString()}.csv`;
    link.click();
}

// Button voor het exporteren van de grafiek
const exportButton = document.getElementById("exportChart");
if (exportButton) {
    exportButton.addEventListener("click", exportChartToCSV);
}

// Functies om de bot te starten en stoppen
function startBot() {
    fetch('/start-bot', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            alert(data.status);
            updateBotStatus(true); // Update status
        })
        .catch(error => {
            console.error("Fout bij starten van de bot:", error);
            alert("Kon de bot niet starten.");
        });
}

function stopBot() {
    fetch('/stop-bot', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            alert(data.status);
            updateBotStatus(false); // Update status
        })
        .catch(error => {
            console.error("Fout bij stoppen van de bot:", error);
            alert("Kon de bot niet stoppen.");
        });
}

// Event listeners voor de start/stop knoppen
const startButton = document.getElementById("startBot");
if (startButton) {
    startButton.addEventListener("click", startBot);
}

const stopButton = document.getElementById("stopBot");
if (stopButton) {
    stopButton.addEventListener("click", stopBot);
}

// Instellingen tabbladen wisselen
document.addEventListener("DOMContentLoaded", function () {
    // Tabbladen wisselen
    document.getElementById("home-tab").addEventListener("click", function() {
        document.getElementById("home-content").style.display = "block";
        document.getElementById("settings-content").style.display = "none";
    });

    document.getElementById("settings-tab").addEventListener("click", function() {
        document.getElementById("home-content").style.display = "none";
        document.getElementById("settings-content").style.display = "block";
        loadSettings();
    });

    // Instellingen opslaan
    document.getElementById("settings-form").addEventListener("submit", function(event) {
        event.preventDefault();

        const settings = {
            trade_percentage: parseFloat(document.getElementById("trade-percentage").value),
            stop_loss_percentage: parseFloat(document.getElementById("stop-loss-percentage").value),
            take_profit_percentage: parseFloat(document.getElementById("take-profit-percentage").value)
        };

        fetch("/api/settings", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(settings)
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message);
        })
        .catch(error => {
            console.error("Fout bij opslaan van instellingen:", error);
            alert("Kon de instellingen niet opslaan.");
        });
    });

    // Instellingen laden bij het openen van de instellingen tab
    function loadSettings() {
        fetch("/api/settings")
            .then(response => response.json())
            .then(settings => {
                document.getElementById("trade-percentage").value = settings.trade_percentage || 0.02;
                document.getElementById("stop-loss-percentage").value = settings.stop_loss_percentage || 0.03;
                document.getElementById("take-profit-percentage").value = settings.take_profit_percentage || 0.05;
            })
            .catch(error => {
                console.error("Fout bij laden van instellingen:", error);
            });
    }
});
