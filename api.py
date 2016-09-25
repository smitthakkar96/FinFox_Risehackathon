from flask import Flask, request, jsonify
import requests
from util import *
import json
import pandas as pd
from collections import namedtuple, defaultdict
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
coBrandSession = None

fixedplans = namedtuple("fixedplans", "discrate irate period")
listofinterestrates = [0.0275, 0.03375, 0.02875, 0.03, 0.03875, 0.04, 0.04125, 0.0425, 0.04375, 0.045, 0.04625, 0.0475,
                       0.04875, 0.05]
listofperiods = [5, 10, 15, 20, 25, 30]
fiveyradjrate40k = 0.03456
sevenyradjrate40k = 0.03412
fiveyradjrate60k = 0.03474
sevenyradjrate60k = 0.03443
fiveyrfedsmedian = 0.0371
fiveyrfedsmode = 0.0296
fiveyradjrate40k *= fiveyrfedsmode / fiveyrfedsmedian
fiveyradjrate60k += fiveyrfedsmode / fiveyrfedsmedian

v = []
for i in listofinterestrates:
    for n in listofperiods:
        m = fixedplans(discrate=1 / (1 + i) ** n, irate=i, period=n)
        v.append(m)


def fixrate(amtborrowed):
    fixedpayments = []
    for i in v:
        fixedpayments.append(
            [(amtborrowed * i[1] / (1 - i[0]**i[2])) / 12, [i[1], i[2]]])
    return fixedpayments


def adjrate(amtborrowed):
    adjpayments = []
    adjpayments.append([(amtborrowed * fiveyradjrate40k / (1 - 1 / (1 + fiveyradjrate40k)
                                                           ** 30)) / 12, "with a 5-year Adjustable plan starting at 2.75%"])
    adjpayments.append([(amtborrowed * sevenyradjrate40k / (1 - 1 / (1 + sevenyradjrate40k)
                                                            ** 30)) / 12, "with a 7-year Adjustable plan starting at 2.88%"])
    adjpayments.append([(amtborrowed * fiveyradjrate60k / (1 - 1 / (1 + fiveyradjrate60k)
                                                           ** 30)) / 12, "with a 5-year Adjustable plan starting at 2.88%"])
    adjpayments.append([(amtborrowed * sevenyradjrate60k / (1 - 1 / (1 + sevenyradjrate60k)
                                                            ** 30)) / 12, "with a 7-year Adjustable plan starting at 3.00%"])
    return adjpayments


def insurancetype(purchase, amtborrowed, upperlimit):
    fp = fixrate(amtborrowed)
    ap = adjrate(amtborrowed)
    retval = 0
    if purchase == "house":
        # monthly payment + monthly property tax + monthly insurance
        map(lambda x: x[0] + float(2127 / 12) + float(952 / 12), fp)
        map(lambda x: x[0] + float(2127 / 12) + float(952 / 12), ap)
        # retval = financingplansfixed(amt)[0] + float(2127/12) + float(952/12)
    elif purchase == "car":
        # monthly payment + monthly insurance
        map(lambda x: x[0] + float(412 / 12) + float(2374 / 12), fp)
        map(lambda x: x[0] + float(412 / 12) + float(2374 / 12), ap)
        # retval = financingplansfixed(amt)[0] + float(412/12) + float(2374/12)
    fp.sort()
    ap.sort()
    final = fp + ap
    final.sort()
    listfinal = list(filter(lambda x: x[0] <= upperlimit, list(final)))[-3:]
    listfinal.reverse()
    retval = []
    for i in listfinal:
        if isinstance(i[1], str):
            retval.append(round(i[0], 2))
            retval.append(int(i[1][7]))
            retval.append("adjustable")
            retval.append(float(i[1][-5:-1]))
            #print("Your monthly payment would be %.2f, %s" % (round(i[0], 2), i[1]))
        else:
            retval.append(round(i[0], 2))
            retval.append(i[1][1])
            retval.append("fixed")
            retval.append(round(i[1][0] * 100, 2))
            #print("Your monthly payment would be %.2f, with a %d-year Fixed Rate of %.3f%%" % (round(i[0], 2), i[1][1], 100 * i[1][0]))
    return retval


@app.route('/api/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')
    user = search(username, password, SandBox)
    if user:
        url = HOST + '/user/login'
        payload = {
            "user": {
                "loginName": user[0]["SandboxUsername"],
                "password": user[0]["SandboxPassword"],
                "locale": "en_US"
            }
        }
        headers = {
            "Content-Type": 'application/json',
            'Authorization': '{cobSession =' + coBrandSession + '}'
        }
        resp = requests.post(url, data=json.dumps(payload), headers=headers)
        resp = resp.json()
        return jsonify({"response": "success", "userSession": resp["user"]["session"]["userSession"]})
    return jsonify({"response": "invalid credentials"}), 401


@app.route('/api/accounts')
def accounts():
    userSession = request.args.get('userSession')
    headers = {
        "Content-Type": 'application/json',
        'Authorization': '{cobSession =' + coBrandSession + ',userSession = ' + userSession + '}'
    }
    url = HOST + '/accounts'
    resp = requests.get(url, headers=headers)

    url = HOST + '/transactions?fromDate=2013-01-01'
    resp = requests.get(url, headers=headers)
    for t in resp.json()["transaction"]:
        credit = defaultdict(int)
        debit = defaultdict(int)
        for r in resp.json()["transaction"]:
            monthAndYear = r["date"].split('-')[0] + "-" + r["date"].split('-')[1]
            if r["baseType"] == 'DEBIT':
                debit[monthAndYear + "," + str(r["accountId"])] += r["amount"]["amount"]
            else:
                credit[monthAndYear + "," + str(r["accountId"])] += r["amount"]["amount"]
    _credit = []
    _debit = []
    for key, value in credit.iteritems():
        temp = {"key" : key.split(',')[1], "val" : value}
        _credit.append(temp)
    for key, value in debit.iteritems():
        temp = {"key" : key.split(',')[1], "val" : value}
        _debit.append(temp)


    return jsonify({"response" : {
        "credit" : _credit,
        "debit" : _debit
    }})


@app.route('/api/transactions')
def transactions():
    userSession = request.args.get('userSession')
    headers = {
        "Content-Type": 'application/json',
        'Authorization': '{cobSession =' + coBrandSession + ',userSession = ' + userSession + '}'
    }
    print headers["Authorization"]
    url = HOST + '/transactions?fromDate=2013-01-01'
    resp = requests.get(url, headers=headers)
    debits = []

    for r in resp.json()["transaction"]:
        if r["baseType"] == 'DEBIT':
            debits.append({"category": categories[r["highLevelCategoryId"]], "amount": r[
                          "amount"]["amount"], "accountId": r["accountId"]})
    print debits
    df = pd.DataFrame(debits)
    all = df.groupby("category").sum().to_dict()["amount"]
    # del all["accountId"]

    accountIds = df["accountId"].unique()
    data = []
    for account in accountIds:
        singleDF = df[df.accountId == account]
        singleDF = singleDF.groupby("category").sum()
        singleDict = singleDF.to_dict()["amount"]
        data.append({account: singleDict})
    data.append({"all": all})
    return jsonify({"response": data})


@app.route('/api/mortageSolutions', methods = ['POST'])
def mortageSolutions():
    userSession = request.json.get('userSession')
    headers = {
        "Content-Type": 'application/json',
        'Authorization': '{cobSession =' + coBrandSession + ',userSession = ' + userSession + '}'
    }
    print headers["Authorization"]
    url = HOST + '/transactions?fromDate=2013-01-01'
    resp = requests.get(url, headers=headers)
    debits = []
    credit = defaultdict(int)
    debit = defaultdict(int)
    for r in resp.json()["transaction"]:
        monthAndYear = r["date"].split('-')[0] + "-" + r["date"].split('-')[1]
        if r["baseType"] == 'DEBIT':
            debit[monthAndYear] += r["amount"]["amount"]
        else:
            credit[monthAndYear] += r["amount"]["amount"]
    upperLimit = int(sum(credit.values()) / len(credit.values()) - sum(debit.values()) / len(debit.values()) * 1.5)
    print upperLimit
    purchaseType = request.json.get('purchaseType')
    amtBorrowed = int(request.json.get('amtBorrowed'))
    returnVal = []
    returnVal = insurancetype(purchaseType, amtBorrowed, upperLimit)
    if not returnVal:
        return jsonify({"response": "We cannot find any mortgage plans that won't comprimise your current lifestyle.", "credit": credit, "debit": debit})
    else:
        return jsonify({"response": returnVal, "credit": sum(credit.values()) / len(credit.values()), "debit": sum(debit.values()) / len(debit.values())})


def search(username, password, people):
    return [element for element in people if element['finFoxUsername'] == username and element['finFoxPassword'] == password]



# let's finish CobrandLogin
url = HOST + '/cobrand/login'
payload = {
    "cobrand": {
        "cobrandLogin": CobrandLogin,
        "cobrandPassword": CobrandPassword,
        "locale": "en_US"
    }
}
headers = {'Content-Type': 'application/json'}
resp = requests.post(url, data=json.dumps(payload), headers=headers)
resp = resp.json()
coBrandSession = resp["session"]["cobSession"]
print coBrandSession
# app.run(debug=True)
