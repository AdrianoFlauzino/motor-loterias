import sys
import os
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# ============================================================
# CONFIGURAÇÕES GERAIS
# ============================================================

# URL base do site de Loterias Online da Caixa
URL_BASE = "https://loteriasonline.caixa.gov.br/"

# Mapeamento de slugs do JSON para URLs relativas/paths do site da Caixa.
# IMPORTANTE: Esses caminhos podem mudar conforme o site da Caixa é atualizado.
# Caso o script não encontre a página correta, acesse o site manualmente,
# navegue até a loteria desejada e copie a URL atualizada.
URLS_LOTERIAS = {
    "megasena": "megasena",
    "lotofacil": "lotofacil",
    "quina": "quina",
    "maismilionaria": "maismilionaria",
    "diadesorte": "diadesorte",
}

# ============================================================
# SELETORES CSS (ATUALIZE CONFORME O SITE DA CAIXA MUDAR)
# ============================================================
# Os seletores abaixo são exemplos baseados na estrutura comum do site.
# Como o site da Caixa utiliza frameworks JS (React/Angular), as classes
# podem mudar frequentemente.
#
# COMO INSPECIONAR E ATUALIZAR OS SELETORES:
# 1. Abra o site no Google Chrome.
# 2. Pressione F12 para abrir as Ferramentas de Desenvolvedor.
# 3. Clique no ícone de "inspecionar elemento" (seta no canto superior esquerdo do painel).
# 4. Passe o mouse sobre o elemento desejado (ex: botão de login, dezena do volante).
# 5. O HTML do elemento será destacado. Clique com o botão direito > Copy > Copy selector.
# 6. Cole o seletor copiado na variável correspondente abaixo.
# ============================================================

SELETORES = {
    # Botão de aceitar cookies (popup inicial)
    "btn_aceitar_cookies": "#onetrust-accept-btn-handler",

    # Login
    "btn_entrar": "button[title='Entrar'], .login-btn, a[href*='login']",
    "input_cpf": "input[name='cpf'], input[id='cpf']",
    "input_senha": "input[name='password'], input[type='password']",
    "btn_logar": "button[type='submit'], button.btn-login",

    # Volante de apostas
    # Cada dezena geralmente é um elemento clicável com um atributo data-numero ou texto igual ao número.
    "dezena_volante": "li[data-numero], div[data-numero]",

    # Botão para adicionar aposta ao carrinho
    "btn_adicionar_carrinho": "button.btn-add-to-cart, button[title='Adicionar ao carrinho'], .add-cart-btn",

    # Indicador de carregamento/loading (overlay)
    "loading_overlay": ".loading-overlay, .spinner",

    # Botão do carrinho para capturar a URL
    "btn_carrinho": "a[href*='carrinho'], .cart-icon, .shopping-cart",
}

# Tempo máximo de espera padrão (em segundos) para elementos aparecerem
TEMPO_ESPERA = 20


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def configurar_navegador():
    """Configura e inicializa o Chrome WebDriver com opções robustas."""
    print("[INFO] Configurando o navegador Chrome...")
    chrome_options = Options()
    # Descomente a linha abaixo para rodar em modo headless (sem interface gráfica)
    # chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.cookies": 1
    })

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(60)
    return driver


def aceitar_cookies(driver, wait):
    """Tenta fechar o popup de cookies se estiver presente."""
    try:
        print("[INFO] Verificando popup de cookies...")
        btn_cookies = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SELETORES["btn_aceitar_cookies"]))
        )
        btn_cookies.click()
        print("[INFO] Cookies aceitos.")
        time.sleep(1)
    except TimeoutException:
        print("[INFO] Popup de cookies não encontrado ou já aceito.")


def fazer_login(driver, wait, cpf, senha):
    """Realiza o login no site da Caixa usando CPF e senha."""
    print("[INFO] Iniciando processo de login...")
    try:
        btn_entrar = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SELETORES["btn_entrar"]))
        )
        btn_entrar.click()
        print("[INFO] Tela de login aberta.")

        input_cpf = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SELETORES["input_cpf"]))
        )
        input_cpf.clear()
        input_cpf.send_keys(cpf)

        input_senha = driver.find_element(By.CSS_SELECTOR, SELETORES["input_senha"])
        input_senha.clear()
        input_senha.send_keys(senha)

        btn_logar = driver.find_element(By.CSS_SELECTOR, SELETORES["btn_logar"])
        btn_logar.click()

        # Aguarda o login ser processado (espera o botão de entrar sumir ou painel do usuário aparecer)
        time.sleep(5)
        print("[INFO] Login realizado com sucesso (presumido).")
    except TimeoutException as e:
        print("[ERRO] Não foi possível encontrar os campos de login. Verifique os seletores CSS.")
        raise e
    except Exception as e:
        print(f"[ERRO] Falha durante o login: {e}")
        raise e


def navegar_para_loteria(driver, wait, slug):
    """Navega até a página da loteria correspondente ao slug."""
    print(f"[INFO] Navegando para a loteria: {slug}...")
    path = URLS_LOTERIAS.get(slug)
    if not path:
        raise ValueError(f"Loteria '{slug}' não suportada. Slugs válidos: {list(URLS_LOTERIAS.keys())}")

    url_loteria = f"{URL_BASE}{path}"
    driver.get(url_loteria)

    # Aguarda o volante carregar
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELETORES["dezena_volante"])))
        print(f"[INFO] Página da loteria {slug} carregada.")
    except TimeoutException:
        print(f"[ERRO] O volante da loteria {slug} não carregou. Verifique a URL e os seletores.")
        raise


def clicar_dezena(driver, wait, numero):
    """Clica em uma dezena específica no volante virtual."""
    # Tenta encontrar a dezena pelo atributo data-numero
    try:
        dezena = driver.find_element(By.CSS_SELECTOR, f"{SELETORES['dezena_volante']}[data-numero='{numero}']")
        driver.execute_script("arguments[0].scrollIntoView(true);", dezena)
        time.sleep(0.2)
        dezena.click()
        return True
    except (NoSuchElementException, ElementClickInterceptedException):
        pass

    # Fallback: tenta encontrar pelo texto do elemento
    try:
        elementos = driver.find_elements(By.CSS_SELECTOR, SELETORES["dezena_volante"])
        for el in elementos:
            if el.text.strip() == str(numero):
                driver.execute_script("arguments[0].scrollIntoView(true);", el)
                time.sleep(0.2)
                el.click()
                return True
    except Exception as e:
        print(f"[ERRO] Falha ao clicar na dezena {numero}: {e}")

    print(f"[ALERTA] Dezena {numero} não encontrada no volante.")
    return False


def aguardar_carregamento(driver, wait):
    """Aguarda possíveis overlays de loading desaparecerem."""
    try:
        overlay = driver.find_element(By.CSS_SELECTOR, SELETORES["loading_overlay"])
        wait.until(EC.invisibility_of_element(overlay))
    except NoSuchElementException:
        # Se não houver overlay, segue o fluxo
        pass
    except TimeoutException:
        print("[ALERTA] Timeout aguardando carregamento, prosseguindo...")


def preencher_aposta(driver, wait, dezenas):
    """Preenche uma aposta clicando nas dezenas e adicionando ao carrinho."""
    print(f"[INFO] Preenchendo aposta com dezenas: {dezenas}")

    # Clica em cada dezena
    for numero in dezenas:
        if not clicar_dezena(driver, wait, numero):
            print(f"[ERRO] Não foi possível selecionar a dezena {numero}. Abortando esta aposta.")
            return False
        time.sleep(0.3)  # Pequena pausa para a animação do site

    # Clica em adicionar ao carrinho
    try:
        btn_add = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, SELETORES["btn_adicionar_carrinho"]))
        )
        btn_add.click()
        print("[INFO] Aposta adicionada ao carrinho.")
        aguardar_carregamento(driver, wait)
        time.sleep(2)
        return True
    except TimeoutException:
        print("[ERRO] Botão 'Adicionar ao carrinho' não encontrado ou não clicável.")
        return False


def obter_url_carrinho(driver, wait):
    """Tenta capturar a URL do carrinho de compras."""
    try:
        btn_carrinho = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SELETORES["btn_carrinho"]))
        )
        href = btn_carrinho.get_attribute("href")
        if href:
            return href
        # Se não houver href, clica para acessar o carrinho e captura a URL
        btn_carrinho.click()
        time.sleep(2)
        return driver.current_url
    except Exception:
        return f"{URL_BASE}carrinho"


def ler_arquivo_json(caminho):
    """Lê e valida o arquivo JSON gerado pelo Motor Analítico."""
    print(f"[INFO] Lendo arquivo JSON: {caminho}")
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)

        if "loteria" not in dados or "apostas" not in dados:
            raise ValueError("JSON inválido: campos 'loteria' e 'apostas' são obrigatórios.")

        print(f"[INFO] Loteria: {dados['loteria']} | Total de apostas: {len(dados['apostas'])}")
        return dados
    except FileNotFoundError:
        print(f"[ERRO] Arquivo não encontrado: {caminho}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"[ERRO] Falha ao decodificar JSON: {e}")
        sys.exit(1)


def obter_credenciais():
    """Obtém CPF e senha via variáveis de ambiente ou input do terminal."""
    cpf = os.getenv("CAIXA_CPF")
    senha = os.getenv("CAIXA_SENHA")

    if not cpf:
        cpf = input("Digite seu CPF (somente números): ").strip()
    if not senha:
        senha = input("Digite sua senha da Caixa: ").strip()

    return cpf, senha


# ============================================================
# FUNÇÃO PRINCIPAL
# ============================================================

def main(caminho_json):
    dados = ler_arquivo_json(caminho_json)
    slug = dados["loteria"].lower()
    apostas = dados["apostas"]

    cpf, senha = obter_credenciais()

    driver = configurar_navegador()
    wait = WebDriverWait(driver, TEMPO_ESPERA)

    apostas_preenchidas = 0
    custo_estimado = 0.0

    try:
        print("[INFO] Acessando o site de Loterias Online da Caixa...")
        driver.get(URL_BASE)
        aceitar_cookies(driver, wait)

        fazer_login(driver, wait, cpf, senha)
        navegar_para_loteria(driver, wait, slug)

        for aposta in apostas:
            aposta_id = aposta.get("id", "?")
            dezenas = aposta.get("dezenas", [])
            print(f"\n[INFO] Processando Aposta #{aposta_id}...")

            sucesso = preencher_aposta(driver, wait, dezenas)
            if sucesso:
                apostas_preenchidas += 1
                # O custo estimado depende da loteria e quantidade de dezenas.
                # Aqui usamos um valor base simplificado; ajuste conforme tabela da Caixa.
                # Exemplo: Mega-Sena 6 dezenas = R$ 5,00 (valor ilustrativo).
                custo_base = 5.0
                custo_estimado += custo_base
            else:
                print(f"[ALERTA] Aposta #{aposta_id} não foi concluída.")

            aguardar_carregamento(driver, wait)

        url_carrinho = obter_url_carrinho(driver, wait)

        # Resumo final
        print("\n" + "=" * 60)
        print("RESUMO DA EXECUÇÃO")
        print("=" * 60)
        print(f"Total de apostas no JSON: {len(apostas)}")
        print(f"Apostas preenchidas:      {apostas_preenchidas}")
        print(f"Custo estimado:           R$ {custo_estimado:.2f} (valor ilustrativo)")
        print(f"URL do carrinho:          {url_carrinho}")
        print("=" * 60)
        print("[INFO] Revise o carrinho no navegador antes de finalizar a compra.")

        # Mantém o navegador aberto para revisão manual
        input("\n[INFO] Pressione ENTER para fechar o navegador...")

    except Exception as e:
        print(f"\n[ERRO CRÍTICO] {e}")
        print("[INFO] O navegador será mantido aberto para inspeção.")
        input("Pressione ENTER para fechar o navegador...")
    finally:
        print("[INFO] Fechando o navegador...")
        driver.quit()


# ============================================================
# PONTO DE ENTRADA
# ============================================================

if __name__ == "__main__":
    # Verifica se o caminho do arquivo JSON foi passado como argumento
    if len(sys.argv) < 2:
        print("Uso: python loteria_selenium.py <caminho_para_arquivo.json>")
        print("Exemplo: python loteria_selenium.py apostas_megasena.json")
        sys.exit(1)

    caminho_arquivo = sys.argv[1]
    main(caminho_arquivo)
