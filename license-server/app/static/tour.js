/* Tour guiado 2.0 — segmentos por página ancorados em [data-tour].
   Auto-inicia no primeiro acesso (window.TOUR.seen === false) com um
   welcome modal ("Fazer o tour" / "Agora não"); o botão "Ver tutorial"
   chama startTour(0). Entre páginas: ?tour=<indice do segmento>. */
(function () {
  const driver = window.driver.js.driver;

  const SEGMENTS = [
    {
      page: "/app/ocorrencias",
      steps: [
        {
          popover: {
            title: "Bem-vindo ao Processador de Ocorrências",
            description:
              "Em ~2 minutos você vê tudo que o sistema faz: Ocorrências, " +
              "VT-Caixa, Códigos e Histórico.<br><br>Você pode rever este " +
              "tour quando quiser no botão <strong>Ver tutorial</strong> da barra lateral.",
            popoverClass: "tour-welcome",
          },
          welcome: true,
        },
        { element: '[data-tour="oc-pdf"]', popover: { title: "1. PDF de jornada",
            description: "Arraste (ou clique e escolha) o relatório PDF de jornada. " +
              "É dele que o sistema extrai as ocorrências de cada RE." } },
        { element: '[data-tour="oc-xlsx"]', popover: { title: "2. Planilha de pedido",
            description: "Esta é a planilha que será preenchida." +
              '<div class="tour-warn">Ela <strong>precisa ter</strong> as colunas ' +
              "<code>Folha RE</code> e <code>MOTIVO</code> na primeira linha — sem elas " +
              "o processamento falha.</div>" } },
        { element: '[data-tour="oc-codigos"]', popover: { title: "3. Códigos de ocorrência",
            description: "Clique nas pílulas para escolher quais códigos entram no MOTIVO " +
              "(FA = Faltas, AT = Atestado...).<br><br>Precisa de um código que não existe? " +
              "Crie na página <strong>Códigos</strong> — ele aparece aqui na hora." } },
        { element: '[data-tour="oc-processar"]', popover: { title: "4. Processar",
            description: "O arquivo entra na fila e uma barra mostra o progresso.<ul>" +
              "<li>Leituras iguais → resultado sai direto.</li>" +
              "<li>Leituras divergentes → você revisa cada diferença antes de gerar.</li>" +
              "</ul>O download fica disponível por 7 dias." } },
        { element: '[data-tour="oc-requisitos"]', popover: { title: "Requisitos sempre à mão",
            description: "Este painel resume o que cada arquivo precisa ter. Os REs do PDF " +
              "que não estiverem na planilha saem na aba <code>Não localizados</code> do resultado." } },
      ],
    },
    {
      page: "/app/vt-caixa",
      steps: [
        { element: '[data-tour="nav-vtcaixa"]', popover: { title: "VT-Caixa",
            description: "Gera o CSV de benefícios de Vale-Transporte para importação no banco." } },
        { element: '[data-tour="vt-fonte"]', popover: { title: "Fonte Nautilus",
            description: "O relatório Nautilus, em <code>.pdf</code> ou Excel." } },
        { element: '[data-tour="vt-cadastral"]', popover: { title: "Cadastro funcional",
            description: "Excel com matrícula (<code>Cód Epr</code>), CPF, RG, endereço e " +
              "nome da mãe — é de onde saem os dados pessoais do CSV." } },
        { element: '[data-tour="vt-processar"]', popover: { title: "Processar",
            description: "Ao concluir, baixe o CSV (codificação latin-1) pronto para o banco." +
              '<div class="tour-warn">Operadora sem código cadastrado sai com o nome original — ' +
              "cadastre o código na página Códigos.</div>" } },
      ],
    },
    {
      page: "/app/codigos",
      steps: [
        { element: '[data-tour="nav-codigos"]', popover: { title: "Códigos",
            description: "Todas as tabelas de referência do sistema, com busca e cópia num clique." } },
        { element: '[data-tour="cod-ocorrencia"]', popover: { title: "Códigos de Ocorrência",
            description: "Os códigos que aparecem no formulário de Ocorrências. Além dos 11 " +
              "embutidos, você pode criar os seus." } },
        { element: '[data-tour="cod-add-ocorrencia"]', popover: { title: "Criar um código",
            description: "Informe o código (até 4 letras), a descrição e se ele leva quantidade " +
              "no MOTIVO (ex.: <code>2 FR</code>) ou não (como AP/LM/FE).<br><br>Vale para todos " +
              "os usuários imediatamente." } },
        { element: '[data-tour="cod-beneficio"]', popover: { title: "Operadora → Código de Benefício",
            description: "Usados no VT-Caixa: quando a operadora (e o valor, se definido) casa, " +
              "o CSV sai com o código no lugar do nome. Personalizados têm prioridade sobre os embutidos." } },
        { element: '[data-tour="cod-depart"]', popover: { title: "Substituições de Departamento",
            description: "Renomeiam departamentos no CSV do VT-Caixa (ex.: nomes de contrato → nomes curtos)." } },
      ],
    },
    {
      page: "/app/historico",
      steps: [
        { element: '[data-tour="nav-historico"]', popover: { title: "Histórico",
            description: "Cada processamento seu fica registrado aqui, com status e link para reabrir." } },
        { element: '[data-tour="hist-filtros"]', popover: { title: "Busca e filtro",
            description: "Procure por nome de arquivo ou filtre por sucesso/erro." } },
        { element: '[data-tour="hist-export"]', popover: { title: "Exportar CSV",
            description: "Baixa o histórico filtrado em CSV." } },
        { element: '[data-tour="btn-tutorial"]', popover: { title: "É isso!",
            description: "Sempre que precisar, clique aqui para rever este tour do início. Bom trabalho!" } },
      ],
    },
  ];

  function markSeen() {
    if (window.TOUR.seen) return;
    window.TOUR.seen = true;
    fetch("/app/tutorial/seen", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "csrf_token=" + encodeURIComponent(window.TOUR.csrf),
    });
  }

  function runSegment(idx) {
    const seg = SEGMENTS[idx];
    const steps = seg.steps.filter(
      (s) => !s.element || document.querySelector(s.element)
    );
    if (!steps.length) { nextSegment(idx); return; }
    const d = driver({
      showProgress: true,
      progressText: "{{current}} de {{total}}",
      nextBtnText: "Próximo",
      prevBtnText: "Anterior",
      doneBtnText: idx === SEGMENTS.length - 1 ? "Concluir" : "Continuar →",
      steps: steps,
      onPopoverRender: (popover, opts) => {
        const stepDef = steps[opts.state.activeIndex];
        if (stepDef && stepDef.welcome) {
          // welcome modal: renomeia o next e adiciona "Agora não"
          popover.nextButton.innerText = "Fazer o tour";
          const skip = document.createElement("button");
          skip.innerText = "Agora não";
          skip.className = "tour-skip-btn";
          skip.addEventListener("click", () => { d.destroy(); markSeen(); });
          popover.footerButtons.appendChild(skip);
        }
      },
      onDestroyed: () => {
        if (d.hasNextStep()) {
          markSeen();           // fechou no meio: marca e para
        } else {
          nextSegment(idx);     // terminou o segmento: próximo
        }
      },
    });
    d.drive();
  }

  function nextSegment(idx) {
    const next = idx + 1;
    if (next >= SEGMENTS.length) { markSeen(); return; }
    window.location.href = SEGMENTS[next].page + "?tour=" + next;
  }

  window.startTour = function (idx) {
    const seg = SEGMENTS[idx || 0];
    if (window.location.pathname !== seg.page) {
      window.location.href = seg.page + "?tour=" + (idx || 0);
      return;
    }
    runSegment(idx || 0);
  };

  document.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    const tourParam = params.get("tour");
    if (tourParam !== null) {
      const idx = parseInt(tourParam, 10);
      if (idx >= 0 && idx < SEGMENTS.length) runSegment(idx);
    } else if (window.TOUR && window.TOUR.seen === false) {
      window.startTour(0);
    }
  });
})();
